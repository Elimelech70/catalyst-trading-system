# ============================================================================
# APPROVAL ALERT HEADING - web_dashboard.py patch
# ============================================================================

# 1. ADD TO STYLES (inside the STYLES = """ string):
# ----------------------------------------------------------------------------

"""
    .alert-heading { 
        color: #ff4444 !important; 
        font-weight: bold; 
        animation: pulse 2s infinite; 
    }
    @keyframes pulse { 
        0%, 100% { opacity: 1; } 
        50% { opacity: 0.7; } 
    }
"""

# 2. WHERE YOU BUILD THE APPROVALS HTML:
# ----------------------------------------------------------------------------
# Find where you create the approvals section and use this pattern:

def build_approvals_section(approvals: list, token: str) -> str:
    """Build approvals HTML with alert styling when pending."""
    approval_count = len(approvals)
    
    if approval_count > 0:
        # Red pulsing heading when approvals pending
        heading = '<h2 class="alert-heading">⚠️ PENDING APPROVALS</h2>'
    else:
        heading = '<h2>Approvals</h2>'
    
    html = heading
    
    if approval_count == 0:
        html += '<div class="empty">No pending approvals</div>'
    else:
        for a in approvals:
            html += f'''
            <div class="card escalation">
                <div class="msg-header">
                    <span class="msg-from">{a["from_agent"]}</span>
                    <span class="msg-time">{format_time(a["created_at"])}</span>
                </div>
                <div class="msg-subject">{a["subject"]}</div>
                <div class="msg-body">{a["body"][:200]}...</div>
                <div class="approval-buttons">
                    <form method="POST" action="/approve/{a["id"]}?token={token}">
                        <button type="submit" class="btn-approve">✓ Approve</button>
                    </form>
                    <form method="POST" action="/deny/{a["id"]}?token={token}">
                        <button type="submit" class="btn-deny">✗ Deny</button>
                    </form>
                </div>
            </div>
            '''
    
    return html


# ============================================================================
# SUMMARY OF CHANGES:
# ============================================================================
#
# 1. Add .alert-heading CSS with red color and pulse animation
# 2. Conditionally apply class="alert-heading" when approval_count > 0
# 
# The heading will:
# - Be normal blue when no approvals pending
# - Turn RED and PULSE when approvals need attention
#
# ============================================================================
