# Security Policy

## Sensitive Data

Do not commit API keys, tokens, cookies, student identity numbers, personal addresses, raw AGH sessions, or unauthorized industrial data.

## Safe Operation

- Critical plant-state changes require verification and explicit human approval.
- The safety shield and controller interlocks must remain active.
- Virtual Modbus is a protocol test only, not a real PLC/DCS validation.
- Physical emergency stop, watchdog, maintenance permission and audit trace are required before field deployment.

## Reporting

Report security issues privately to the team before public disclosure.
