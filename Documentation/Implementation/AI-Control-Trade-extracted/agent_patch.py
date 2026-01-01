# agent.py - ONE LINE CHANGE REQUIRED

"""
This is the ONLY change needed in agent.py to enable position monitoring.

FIND this code block in the run_cycle() method (around line ~180-190):

    # Initialize executor for this cycle
    self.executor = ToolExecutor(
        cycle_id=self.cycle_id,
        alert_callback=self._send_alert,
    )

CHANGE IT TO:

    # Initialize executor for this cycle
    self.executor = ToolExecutor(
        cycle_id=self.cycle_id,
        alert_callback=self._send_alert,
        agent=self,  # <-- ADD THIS LINE
    )

That's it! This passes a reference to the TradingAgent so the executor
can access the anthropic client for Haiku consultations.
"""

# Here's the exact diff:

AGENT_DIFF = """
--- a/agent.py
+++ b/agent.py
@@ -XXX,XX +XXX,XX @@ class TradingAgent:
         # Initialize executor for this cycle
         self.executor = ToolExecutor(
             cycle_id=self.cycle_id,
             alert_callback=self._send_alert,
+            agent=self,
         )
"""

# That's the only change needed to agent.py!
