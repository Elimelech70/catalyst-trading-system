 Setup Complete

  ┌────────────────┬───────────────────────────────────┐
  │     Detail     │               Value               │
  ├────────────────┼───────────────────────────────────┤
  │ Container      │ claude-code-viewer-app-1          │
  ├────────────────┼───────────────────────────────────┤
  │ URL            │ http://localhost:3400             │
  ├────────────────┼───────────────────────────────────┤
  │ Port           │ 3400                              │
  ├────────────────┼───────────────────────────────────┤
  │ Data source    │ /root/.claude (mounted read-only) │
  ├────────────────┼───────────────────────────────────┤
  │ Projects found │ 2                                 │
  ├────────────────┼───────────────────────────────────┤
  │ Sessions found │ 8                                 │
  ├────────────────┼───────────────────────────────────┤
  │ Restart policy │ unless-stopped (survives reboots) │
  └────────────────┴───────────────────────────────────┘

  What was done:
  1. Pulled claude-code-viewer-setup.md from GitHub
  2. Cloned the https://github.com/d-kimuson/claude-code-viewer repo to /root/claude-code-viewer
  3. Fixed two Docker build issues (lefthook prepare script needing a git repo during install, and --ignore-scripts for prune)
  4. Mounted ~/.claude read-only into the container so it can read your conversation history
  5. Built and started the container on port 3400

  To access from other devices on the same network, use http://<droplet-ip>:3400. Note: no authentication is built in, so only use on trusted networks.

External access through Nginx

 All set. The Claude Code Viewer is now externally accessible just like your dashboard:                                                                                                                    
                                                                                                                                                                                                            
  ┌────────────────────┬───────────────────────────┐                                                                                                                                                        
  │      Service       │            URL            │                                                                                                                                                        
  ├────────────────────┼───────────────────────────┤                                                                                                                                                        
  │ Catalyst Dashboard │ http://68.183.177.11:8080 │                                                                                                                                                        
  ├────────────────────┼───────────────────────────┤                                                                                                                                                        
  │ Claude Code Viewer │ http://68.183.177.11:8081 │                                                                                                                                                        
  └────────────────────┴───────────────────────────┘

  The Nginx proxy handles WebSocket upgrades for live session updates. Port 8081 is open in the firewall. No authentication is configured (same as the dashboard) — access from any browser on your network.

✻ Brewed for 43s