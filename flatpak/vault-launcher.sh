#!/bin/sh
export PYTHONPATH=/app/share/vault-launcher${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m vault_launcher "$@"
