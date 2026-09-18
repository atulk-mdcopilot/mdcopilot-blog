#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
output_dir="${BACKUP_DIR:-backups}"
umask 077
mkdir -p "$output_dir"
output="$output_dir/mdcopilot-blog-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' > "$output.partial"
mv "$output.partial" "$output"
shasum -a 256 "$output" > "$output.sha256"
printf 'Backup written: %s\n' "$output"
