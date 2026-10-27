# AEGIS Network Architecture

## Overview
The AEGIS system utilizes a **Single Container, Dual Directory** architecture to maximize resource efficiency (saving ~300-500MB RAM per additional instance) while maintaining strict data isolation between trading environments (e.g., Nasdaq and XAUUSD).

## Architecture Wireframe

```mermaid
graph TD
    User[User Browser] -->|HTTPS| Nginx[Nginx Reverse Proxy]
    Nginx -->|Port 9191| BridgeND[Python Bridge ND]
    Nginx -->|Port 9192| BridgeXAU[Python Bridge XAU]
    Nginx -->|Port 9091| VNC[KasmVNC Web Client]

    subgraph Docker Network: aegis_default
        BridgeND -->|HTTP WebRequest| MT5_ND[MT5 ND: /config/mt5_nd]
        BridgeXAU -->|HTTP WebRequest| MT5_XAU[MT5 XAU: /config/mt5_xau]
        MT5_ND -.->|Shared Wine/Xvnc| MT5_XAU
        VNC -->|DISPLAY=:1| MT5_ND
        VNC -->|DISPLAY=:1| MT5_XAU
    end

    MT5_ND -->|Writes| CSV_ND[(score_log.csv)]
    MT5_XAU -->|Writes| CSV_XAU[(score_log.csv)]
    BridgeND -->|Reads| CSV_ND
    BridgeXAU -->|Reads| CSV_XAU
    BridgeND -->|API| Dashboard[Dashboard UI]
    BridgeXAU -->|API| Dashboard
```

## Key Components
1. **Nginx Reverse Proxy**: Routes external HTTPS traffic to internal Docker ports.
2. **KasmVNC (6901 -> 9091)**: Shared X11/Wine session to conserve RAM.
3. **Isolated Directories**: /config/mt5_nd and /config/mt5_xau prevent file overwrites.
4. **Python Bridges**: Separate instances ensure data streams do not mix.

## Known Issues
- **Scan Analytics**: Currently under active troubleshooting. Data pipeline from MT5 to Bridge analytics is being investigated.

## Standard Operating Procedures (SOP)
1. **Version Sync**: Match version in #property version and Print() statements.
2. **Overwrite Method**: Bypass Wine locks by streaming content:
   cat file.mq5 | docker exec -i container sh -c 'cat > /path/to/file.mq5'
3. **Verify**: docker exec container grep "version" /path/to/file.mq5
4. **WebRequest Allowlist**: Add Bridge URL in MT5 Tools -> Options -> Expert Advisors.
