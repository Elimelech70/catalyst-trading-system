#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: order_handler.py
Version: 1.0.0
Last Updated: 2025-12-27
Purpose: Order handling module that uses orders table (C1 fix)

REVISION HISTORY:
v1.0.0 (2025-12-27) - Initial creation for C1 fix
  - Creates orders in orders table FIRST
  - Submits to Alpaca
  - Updates order with Alpaca response
  - Creates position ONLY on fill
  - Links order to position

ARCHITECTURE:
This module implements ARCHITECTURE-RULES.md Rule 1: Orders ≠ Positions
- Order records are created BEFORE submitting to Alpaca
- Position records are created ONLY when order fills
- All order tracking is in the orders table

USAGE:
    from order_handler import OrderHandler
    
    handler = OrderHandler(db_pool, alpaca_trader)
    
    # Submit entry order
    order = await handler.submit_entry_order(
        cycle_id="20251227-001",
        symbol="AAPL",
        side="buy",
        quantity=100,
        entry_price=150.00,
        stop_loss=145.00,
        take_profit=160.00
    )
    
    # Process fill
    await handler.process_order_fill(order['order_id'], fill_data)
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# ORDER HANDLER CLASS
# ============================================================================

class OrderHandler:
    """
    Handles order lifecycle following C1 fix architecture.
    
    Flow:
    1. Create order record (status='created')
    2. Submit to Alpaca
    3. Update order with Alpaca response (status='submitted')
    4. Wait for fill (via sync task)
    5. On fill: Update order, create position, link order to position
    """

    def __init__(self, db_pool: asyncpg.Pool, alpaca_trader):
        """
        Initialize order handler.
        
        Args:
            db_pool: Database connection pool
            alpaca_trader: AlpacaTrader instance
        """
        self.db_pool = db_pool
        self.alpaca_trader = alpaca_trader

    async def submit_entry_order(
        self,
        cycle_id: str,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = 'market'
    ) -> Dict[str, Any]:
        """
        Submit entry order following C1 architecture.
        
        CRITICAL: Creates order record FIRST, then submits to Alpaca.
        Position is NOT created until order fills.
        
        Args:
            cycle_id: Trading cycle ID
            symbol: Stock ticker
            side: 'buy' or 'sell' (or 'long'/'short')
            quantity: Number of shares
            entry_price: Limit price (None for market order)
            stop_loss: Stop-loss price (required for bracket)
            take_profit: Take-profit price (required for bracket)
            order_type: 'market', 'limit', or 'bracket' (default: market)
            
        Returns:
            Order dict with order_id, status, alpaca_order_id, etc.
        """
        # Determine order class
        is_bracket = stop_loss is not None and take_profit is not None
        order_class = 'bracket' if is_bracket else 'simple'
        actual_order_type = 'limit' if entry_price else 'market'
        
        # Map side for database storage
        db_side = 'buy' if side.lower() in ('buy', 'long') else 'sell'
        
        async with self.db_pool.acquire() as conn:
            # Get security_id
            security_id = await conn.fetchval(
                "SELECT get_or_create_security($1)", symbol
            )
            if not security_id:
                raise ValueError(f"Failed to get security_id for {symbol}")

            # ===============================================================
            # STEP 1: Create order record FIRST (before submitting to Alpaca)
            # ===============================================================
            order_id = await conn.fetchval("""
                INSERT INTO orders (
                    security_id,
                    cycle_id,
                    side,
                    order_type,
                    order_class,
                    order_purpose,
                    quantity,
                    limit_price,
                    stop_price,
                    status,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'created', NOW())
                RETURNING order_id
            """,
                security_id,
                cycle_id,
                db_side,
                actual_order_type,
                order_class,
                'entry',
                quantity,
                entry_price,
                stop_loss  # Store stop_loss as reference
            )
            
            logger.info(
                f"[ORDER] Created order {order_id} for {symbol} "
                f"(side={db_side}, qty={quantity}, type={order_class})"
            )

            # ===============================================================
            # STEP 2: Submit to Alpaca
            # ===============================================================
            alpaca_order_id = None
            alpaca_status = "not_submitted"
            error_msg = None

            if self.alpaca_trader and self.alpaca_trader.is_enabled():
                try:
                    if is_bracket:
                        # Submit bracket order
                        alpaca_result = await self.alpaca_trader.submit_bracket_order(
                            symbol=symbol,
                            quantity=quantity,
                            side=side,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit
                        )
                    else:
                        # Submit simple market order
                        alpaca_result = await self.alpaca_trader.submit_market_order(
                            symbol=symbol,
                            quantity=quantity,
                            side=side
                        )

                    alpaca_order_id = alpaca_result['order_id']
                    alpaca_status = alpaca_result['status']

                    # ===============================================================
                    # STEP 3: Update order with Alpaca response
                    # ===============================================================
                    await conn.execute("""
                        UPDATE orders SET
                            alpaca_order_id = $1,
                            status = 'submitted',
                            submitted_at = NOW(),
                            updated_at = NOW(),
                            metadata = jsonb_build_object(
                                'alpaca_status', $2,
                                'entry_price', $3,
                                'stop_loss', $4,
                                'take_profit', $5
                            )
                        WHERE order_id = $6
                    """,
                        alpaca_order_id,
                        alpaca_status,
                        entry_price,
                        stop_loss,
                        take_profit,
                        order_id
                    )

                    logger.info(
                        f"[ORDER] Submitted to Alpaca: order_id={order_id}, "
                        f"alpaca_order_id={alpaca_order_id}, status={alpaca_status}"
                    )

                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        f"[ORDER] Alpaca submission failed for order {order_id}: {e}",
                        exc_info=True
                    )

                    # Update order with error status
                    await conn.execute("""
                        UPDATE orders SET
                            status = 'rejected',
                            rejection_reason = $1,
                            updated_at = NOW()
                        WHERE order_id = $2
                    """, error_msg, order_id)

                    alpaca_status = "error"
            else:
                logger.warning(
                    f"[ORDER] Alpaca not enabled - order {order_id} created in DB only"
                )
                alpaca_status = "alpaca_disabled"

                await conn.execute("""
                    UPDATE orders SET
                        status = 'created',
                        metadata = jsonb_build_object('alpaca_enabled', false),
                        updated_at = NOW()
                    WHERE order_id = $1
                """, order_id)

        return {
            "success": alpaca_status not in ("error", "rejected"),
            "order_id": order_id,
            "alpaca_order_id": alpaca_order_id,
            "symbol": symbol,
            "side": db_side,
            "quantity": quantity,
            "order_type": actual_order_type,
            "order_class": order_class,
            "status": alpaca_status,
            "error": error_msg
        }

    async def process_order_fill(
        self,
        order_id: int,
        filled_qty: int,
        filled_avg_price: float,
        filled_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Process an order fill - create position if entry order.
        
        CRITICAL: Position is created HERE, not in submit_entry_order.
        
        Args:
            order_id: Database order ID
            filled_qty: Number of shares filled
            filled_avg_price: Average fill price
            filled_at: Fill timestamp (default: now)
            
        Returns:
            Result dict with position_id if created
        """
        filled_at = filled_at or datetime.utcnow()

        async with self.db_pool.acquire() as conn:
            # Get order details
            order = await conn.fetchrow("""
                SELECT o.*, s.symbol
                FROM orders o
                JOIN securities s ON o.security_id = s.security_id
                WHERE o.order_id = $1
            """, order_id)

            if not order:
                raise ValueError(f"Order not found: {order_id}")

            # ===============================================================
            # STEP 1: Update order as filled
            # ===============================================================
            status = 'filled' if filled_qty == order['quantity'] else 'partial_fill'

            await conn.execute("""
                UPDATE orders SET
                    status = $1,
                    filled_qty = $2,
                    filled_avg_price = $3,
                    filled_at = $4,
                    updated_at = NOW()
                WHERE order_id = $5
            """, status, filled_qty, filled_avg_price, filled_at, order_id)

            logger.info(
                f"[ORDER] Order {order_id} filled: qty={filled_qty}, "
                f"price={filled_avg_price}, status={status}"
            )

            position_id = None

            # ===============================================================
            # STEP 2: If entry order, create position
            # ===============================================================
            if order['order_purpose'] == 'entry' and order['position_id'] is None:
                # Map order side to position side
                position_side = 'long' if order['side'] == 'buy' else 'short'

                # Get stop_loss and take_profit from metadata
                metadata = order.get('metadata', {}) or {}
                stop_loss = metadata.get('stop_loss')
                take_profit = metadata.get('take_profit')

                # Calculate risk amount
                risk_amount = Decimal('0')
                if stop_loss and filled_avg_price:
                    risk_per_share = abs(float(filled_avg_price) - float(stop_loss))
                    risk_amount = Decimal(str(risk_per_share * filled_qty))

                position_id = await conn.fetchval("""
                    INSERT INTO positions (
                        cycle_id,
                        security_id,
                        side,
                        quantity,
                        entry_price,
                        entry_time,
                        stop_loss,
                        take_profit,
                        risk_amount,
                        status,
                        created_at,
                        opened_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'open', NOW(), $6)
                    RETURNING position_id
                """,
                    order['cycle_id'],
                    order['security_id'],
                    position_side,
                    filled_qty,
                    filled_avg_price,
                    filled_at,
                    stop_loss,
                    take_profit,
                    risk_amount
                )

                logger.info(
                    f"[ORDER] Position {position_id} created for order {order_id} "
                    f"({order['symbol']} {position_side} {filled_qty}@{filled_avg_price})"
                )

                # ===============================================================
                # STEP 3: Link order to position
                # ===============================================================
                await conn.execute("""
                    UPDATE orders SET
                        position_id = $1,
                        updated_at = NOW()
                    WHERE order_id = $2
                """, position_id, order_id)

                # Update cycle metrics
                await conn.execute("""
                    UPDATE trading_cycles SET
                        current_positions = current_positions + 1,
                        used_risk_budget = used_risk_budget + $1,
                        current_exposure = current_exposure + $2
                    WHERE cycle_id = $3
                """,
                    risk_amount,
                    Decimal(str(filled_avg_price * filled_qty)),
                    order['cycle_id']
                )

            # ===============================================================
            # STEP 4: If exit order, close position
            # ===============================================================
            elif order['order_purpose'] in ('stop_loss', 'take_profit', 'exit'):
                if order['position_id']:
                    # Calculate realized P&L
                    position = await conn.fetchrow("""
                        SELECT entry_price, quantity, side
                        FROM positions
                        WHERE position_id = $1
                    """, order['position_id'])

                    if position:
                        entry_price = float(position['entry_price'])
                        if position['side'] == 'long':
                            realized_pnl = (filled_avg_price - entry_price) * filled_qty
                        else:
                            realized_pnl = (entry_price - filled_avg_price) * filled_qty

                        await conn.execute("""
                            UPDATE positions SET
                                status = 'closed',
                                exit_price = $1,
                                exit_time = $2,
                                closed_at = $2,
                                realized_pnl = $3,
                                close_reason = $4,
                                updated_at = NOW()
                            WHERE position_id = $5
                        """,
                            filled_avg_price,
                            filled_at,
                            realized_pnl,
                            order['order_purpose'].upper(),
                            order['position_id']
                        )

                        logger.info(
                            f"[ORDER] Position {order['position_id']} closed: "
                            f"exit_price={filled_avg_price}, pnl={realized_pnl:.2f}"
                        )

        return {
            "success": True,
            "order_id": order_id,
            "status": status,
            "filled_qty": filled_qty,
            "filled_avg_price": filled_avg_price,
            "position_id": position_id
        }

    async def sync_order_status(self, order_id: int) -> Dict[str, Any]:
        """
        Sync order status with Alpaca.
        
        Args:
            order_id: Database order ID
            
        Returns:
            Updated order status
        """
        async with self.db_pool.acquire() as conn:
            order = await conn.fetchrow("""
                SELECT order_id, alpaca_order_id, status
                FROM orders
                WHERE order_id = $1
            """, order_id)

            if not order or not order['alpaca_order_id']:
                return {"success": False, "error": "Order not found or no Alpaca ID"}

            if not self.alpaca_trader or not self.alpaca_trader.is_enabled():
                return {"success": False, "error": "Alpaca not enabled"}

            try:
                # Get status from Alpaca
                alpaca_status = await self.alpaca_trader.get_order_status(
                    order['alpaca_order_id']
                )

                new_status = alpaca_status['status']
                filled_qty = alpaca_status.get('filled_qty', 0)
                filled_avg_price = alpaca_status.get('filled_avg_price')

                # Update if status changed
                if new_status != order['status']:
                    await conn.execute("""
                        UPDATE orders SET
                            status = $1,
                            filled_qty = $2,
                            filled_avg_price = $3,
                            updated_at = NOW()
                        WHERE order_id = $4
                    """, new_status, filled_qty, filled_avg_price, order_id)

                    logger.info(
                        f"[ORDER] Order {order_id} status updated: "
                        f"{order['status']} -> {new_status}"
                    )

                    # Process fill if needed
                    if new_status == 'filled' and filled_avg_price:
                        await self.process_order_fill(
                            order_id, filled_qty, filled_avg_price
                        )

                return {
                    "success": True,
                    "order_id": order_id,
                    "old_status": order['status'],
                    "new_status": new_status,
                    "filled_qty": filled_qty,
                    "filled_avg_price": filled_avg_price
                }

            except Exception as e:
                logger.error(f"[ORDER] Failed to sync order {order_id}: {e}")
                return {"success": False, "error": str(e)}
