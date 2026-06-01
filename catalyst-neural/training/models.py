"""
Catalyst Neural — Network Architecture

Four specialized encoders + fusion network.
Total ~1M parameters. Inference <5ms on CPU.

"Don't tell the network what to see. Show it what happened.
 Let it find what matters."
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from training.dataset import (
    NUM_MACRO_FEATURES, NEWS_FEATURE_DIM,
    NUM_NEWS_CATEGORIES, NUM_SECURITY_FEATURES,
)


class TimeSeriesEncoder(nn.Module):
    """
    1D CNN over a window of OHLCV candles.

    Input:  (batch, lookback, 5)
    Output: (batch, embed_dim)
    """

    def __init__(self, in_channels=5, embed_dim=128):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, 32, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(32)
        self.conv2 = nn.Conv1d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(64)
        self.conv3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(128)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.2)
        self.fc = nn.Linear(128, embed_dim)

    def forward(self, x):
        # (batch, lookback, 5) -> (batch, 5, lookback)
        x = x.transpose(1, 2)
        x = F.gelu(self.bn1(self.conv1(x)))
        x = F.gelu(self.bn2(self.conv2(x)))
        x = F.gelu(self.bn3(self.conv3(x)))
        x = self.pool(x).squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)


class NewsEncoder(nn.Module):
    """
    Bag-of-character-ngrams encoder.

    Input:  (batch, NEWS_FEATURE_DIM)
    Output: (batch, embed_dim)
    """

    def __init__(self, input_dim=NEWS_FEATURE_DIM, embed_dim=128, hidden_dim=256):
        super().__init__()
        self.projection = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, embed_dim)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        x = F.gelu(self.bn1(self.projection(x)))
        x = self.dropout(x)
        x = F.gelu(self.bn2(self.fc1(x)))
        x = self.dropout(x)
        return self.fc2(x)


class MacroEncoder(nn.Module):
    """
    MLP over macro regime snapshot.

    Input:  (batch, NUM_MACRO_FEATURES)
    Output: (batch, embed_dim)
    """

    def __init__(self, input_dim=NUM_MACRO_FEATURES, embed_dim=64, hidden_dim=64):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, embed_dim)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = F.gelu(self.bn1(self.fc1(x)))
        x = self.dropout(x)
        x = F.gelu(self.bn2(self.fc2(x)))
        return self.fc3(x)


class FusionNetwork(nn.Module):
    """
    Combines encoder outputs into predictions.

    Input:  (batch, ts_dim + news_dim + macro_dim)
    Output: returns (batch, num_horizons), confidence (batch, 1)
    """

    def __init__(self, input_dim=320, hidden_dim=256, num_horizons=5):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)

        # Residual block
        self.res_fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.res_bn1 = nn.BatchNorm1d(hidden_dim)
        self.res_fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.res_bn2 = nn.BatchNorm1d(hidden_dim)

        self.dropout = nn.Dropout(0.3)

        self.return_head = nn.Linear(hidden_dim, num_horizons)
        self.confidence_head = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        x = F.gelu(self.bn1(self.input_proj(x)))

        residual = x
        x = F.gelu(self.res_bn1(self.res_fc1(x)))
        x = self.dropout(x)
        x = self.res_bn2(self.res_fc2(x))
        x = F.gelu(x + residual)

        x = self.dropout(x)

        returns = self.return_head(x)
        confidence = torch.sigmoid(self.confidence_head(x))

        return returns, confidence


class CatalystNet(nn.Module):
    """
    Complete Catalyst Neural network.
    ~1M parameters. <5ms CPU inference.
    """

    def __init__(self, lookback=60, ts_embed_dim=128,
                 news_input_dim=NEWS_FEATURE_DIM, news_embed_dim=128,
                 macro_input_dim=NUM_MACRO_FEATURES, macro_embed_dim=64,
                 fusion_hidden=256, num_horizons=5):
        super().__init__()

        self.ts_encoder = TimeSeriesEncoder(in_channels=5, embed_dim=ts_embed_dim)
        self.news_encoder = NewsEncoder(input_dim=news_input_dim, embed_dim=news_embed_dim)
        self.macro_encoder = MacroEncoder(input_dim=macro_input_dim, embed_dim=macro_embed_dim)

        fusion_input = ts_embed_dim + news_embed_dim + macro_embed_dim
        self.fusion = FusionNetwork(
            input_dim=fusion_input, hidden_dim=fusion_hidden,
            num_horizons=num_horizons
        )

    def forward(self, candles, macro, news):
        ts_embed = self.ts_encoder(candles)
        news_embed = self.news_encoder(news)
        macro_embed = self.macro_encoder(macro)

        fused = torch.cat([ts_embed, news_embed, macro_embed], dim=1)
        return self.fusion(fused)

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def encoder_parameter_counts(self):
        return {
            "time_series": sum(p.numel() for p in self.ts_encoder.parameters()),
            "news": sum(p.numel() for p in self.news_encoder.parameters()),
            "macro": sum(p.numel() for p in self.macro_encoder.parameters()),
            "fusion": sum(p.numel() for p in self.fusion.parameters()),
        }


# =============================================================================
# v0.3 — Candle Model (multi-timeframe direction + return prediction)
# =============================================================================


class MultiResolutionEncoder(nn.Module):
    """
    Wraps one TimeSeriesEncoder per timeframe, concatenates outputs.

    Input:  list of (batch, lookback, 5) tensors — one per timeframe
    Output: (batch, num_timeframes * embed_dim)
    """

    def __init__(self, num_timeframes=2, embed_dim=64):
        super().__init__()
        self.encoders = nn.ModuleList([
            TimeSeriesEncoder(in_channels=5, embed_dim=embed_dim)
            for _ in range(num_timeframes)
        ])

    def forward(self, candle_list):
        embeddings = [enc(c) for enc, c in zip(self.encoders, candle_list)]
        return torch.cat(embeddings, dim=1)


class CandleModel(nn.Module):
    """
    v0.3 Candle Model — When to trade.

    Multi-timeframe OHLCV → direction + forward returns + confidence.
    ~130K parameters. <1ms CPU inference.

    Inputs:
        candles_5m:  (batch, lookback, 5)
        candles_15m: (batch, lookback, 5)

    Outputs:
        direction_logits: (batch, 3)  — bullish / bearish / neutral
        pred_returns:     (batch, 3)  — 5m, 15m, 1h forward returns
        confidence:       (batch, 1)  — sigmoid confidence
    """

    NUM_DIRECTIONS = 3   # bullish=0, bearish=1, neutral=2
    NUM_RETURN_HORIZONS = 3  # 5m, 15m, 1h

    def __init__(self, num_timeframes=2, embed_dim=64, fusion_hidden=128):
        super().__init__()

        self.multi_res = MultiResolutionEncoder(
            num_timeframes=num_timeframes, embed_dim=embed_dim
        )

        fusion_input = num_timeframes * embed_dim  # 128

        # Fusion MLP with residual
        self.input_proj = nn.Linear(fusion_input, fusion_hidden)
        self.bn1 = nn.BatchNorm1d(fusion_hidden)

        self.res_fc1 = nn.Linear(fusion_hidden, fusion_hidden)
        self.res_bn1 = nn.BatchNorm1d(fusion_hidden)
        self.res_fc2 = nn.Linear(fusion_hidden, fusion_hidden)
        self.res_bn2 = nn.BatchNorm1d(fusion_hidden)

        self.dropout = nn.Dropout(0.3)

        # Three output heads
        self.direction_head = nn.Linear(fusion_hidden, self.NUM_DIRECTIONS)
        self.return_head = nn.Linear(fusion_hidden, self.NUM_RETURN_HORIZONS)
        self.confidence_head = nn.Linear(fusion_hidden, 1)

    def forward(self, candles_5m, candles_15m):
        fused = self.multi_res([candles_5m, candles_15m])

        x = F.gelu(self.bn1(self.input_proj(fused)))

        residual = x
        x = F.gelu(self.res_bn1(self.res_fc1(x)))
        x = self.dropout(x)
        x = self.res_bn2(self.res_fc2(x))
        x = F.gelu(x + residual)
        x = self.dropout(x)

        direction_logits = self.direction_head(x)
        pred_returns = self.return_head(x)
        confidence = torch.sigmoid(self.confidence_head(x))

        return direction_logits, pred_returns, confidence

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def encoder_parameter_counts(self):
        return {
            "encoder_5m": sum(p.numel() for p in self.multi_res.encoders[0].parameters()),
            "encoder_15m": sum(p.numel() for p in self.multi_res.encoders[1].parameters()),
            "fusion": (
                sum(p.numel() for p in [self.input_proj.weight, self.input_proj.bias,
                    self.bn1.weight, self.bn1.bias,
                    self.res_fc1.weight, self.res_fc1.bias,
                    self.res_bn1.weight, self.res_bn1.bias,
                    self.res_fc2.weight, self.res_fc2.bias,
                    self.res_bn2.weight, self.res_bn2.bias])
            ),
            "direction_head": sum(p.numel() for p in self.direction_head.parameters()),
            "return_head": sum(p.numel() for p in self.return_head.parameters()),
            "confidence_head": sum(p.numel() for p in self.confidence_head.parameters()),
        }


# =============================================================================
# v0.4 — Context-Conditioned Candle Model
#   architecture: Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md
# =============================================================================


class ContextEncoder(nn.Module):
    """
    Encodes (news_context, security_context) into a dense vector.

    Input:  news_ctx (batch, 16), security_ctx (batch, 18) → concat (batch, 34)
    Output: (batch, embed_dim) — default 32
    Param count: ~5K (architecture Section 9.4 budget)
    """

    def __init__(self, news_dim=NUM_NEWS_CATEGORIES, security_dim=NUM_SECURITY_FEATURES,
                 embed_dim=32, hidden_dim=64):
        super().__init__()
        input_dim = news_dim + security_dim
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, embed_dim)
        self.dropout = nn.Dropout(0.2)

    def forward(self, news_ctx, security_ctx):
        x = torch.cat([news_ctx, security_ctx], dim=1)
        x = F.gelu(self.bn1(self.fc1(x)))
        x = self.dropout(x)
        x = F.gelu(self.bn2(self.fc2(x)))
        return self.fc3(x)


class CandleModelV04(nn.Module):
    """
    v0.4 Candle Model — context-conditioned.

    Same dual-timeframe candle encoder as v0.3, plus a ContextEncoder for
    (news_context, security_context). The context embedding is concatenated
    to the fused candle representation BEFORE the fusion MLP. Option 1 in
    architecture Section 5.2 (concatenation).

    Inputs:
        candles_5m:       (batch, lookback, 5)
        candles_15m:      (batch, lookback, 5)
        news_context:     (batch, 16)
        security_context: (batch, 18)

    Outputs (unchanged from v0.3):
        direction_logits: (batch, 3)
        pred_returns:     (batch, 3) — 5m, 15m, 1h
        confidence:       (batch, 1)
    """

    NUM_DIRECTIONS = 3
    NUM_RETURN_HORIZONS = 3
    VERSION = "0.4"

    def __init__(self, num_timeframes=2, embed_dim=64, context_embed_dim=32,
                 fusion_hidden=128):
        super().__init__()

        self.multi_res = MultiResolutionEncoder(
            num_timeframes=num_timeframes, embed_dim=embed_dim
        )
        self.context_encoder = ContextEncoder(embed_dim=context_embed_dim)

        # Fusion input: candle_fused (num_timeframes * embed_dim = 128)
        #             + context_embed (32)
        #             = 160
        fusion_input = num_timeframes * embed_dim + context_embed_dim

        self.input_proj = nn.Linear(fusion_input, fusion_hidden)
        self.bn1 = nn.BatchNorm1d(fusion_hidden)

        self.res_fc1 = nn.Linear(fusion_hidden, fusion_hidden)
        self.res_bn1 = nn.BatchNorm1d(fusion_hidden)
        self.res_fc2 = nn.Linear(fusion_hidden, fusion_hidden)
        self.res_bn2 = nn.BatchNorm1d(fusion_hidden)

        self.dropout = nn.Dropout(0.3)

        self.direction_head = nn.Linear(fusion_hidden, self.NUM_DIRECTIONS)
        self.return_head = nn.Linear(fusion_hidden, self.NUM_RETURN_HORIZONS)
        self.confidence_head = nn.Linear(fusion_hidden, 1)

    def forward(self, candles_5m, candles_15m, news_context, security_context):
        candle_fused = self.multi_res([candles_5m, candles_15m])    # (B, 128)
        ctx_embed = self.context_encoder(news_context, security_context)  # (B, 32)
        fused = torch.cat([candle_fused, ctx_embed], dim=1)         # (B, 160)

        x = F.gelu(self.bn1(self.input_proj(fused)))

        residual = x
        x = F.gelu(self.res_bn1(self.res_fc1(x)))
        x = self.dropout(x)
        x = self.res_bn2(self.res_fc2(x))
        x = F.gelu(x + residual)
        x = self.dropout(x)

        direction_logits = self.direction_head(x)
        pred_returns = self.return_head(x)
        confidence = torch.sigmoid(self.confidence_head(x))

        return direction_logits, pred_returns, confidence

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def encoder_parameter_counts(self):
        return {
            "encoder_5m": sum(p.numel() for p in self.multi_res.encoders[0].parameters()),
            "encoder_15m": sum(p.numel() for p in self.multi_res.encoders[1].parameters()),
            "context_encoder": sum(p.numel() for p in self.context_encoder.parameters()),
            "fusion": (
                sum(p.numel() for p in [self.input_proj.weight, self.input_proj.bias,
                    self.bn1.weight, self.bn1.bias,
                    self.res_fc1.weight, self.res_fc1.bias,
                    self.res_bn1.weight, self.res_bn1.bias,
                    self.res_fc2.weight, self.res_fc2.bias,
                    self.res_bn2.weight, self.res_bn2.bias])
            ),
            "direction_head": sum(p.numel() for p in self.direction_head.parameters()),
            "return_head": sum(p.numel() for p in self.return_head.parameters()),
            "confidence_head": sum(p.numel() for p in self.confidence_head.parameters()),
        }
