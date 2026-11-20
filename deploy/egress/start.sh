#!/bin/sh
# egress-proxy entry point (package 12, C16): turns EGRESS_ALLOWLIST into Squid's allowlist
# and starts Squid in the foreground. Fail-loud: an empty or malformed list stops the
# container instead of starting a proxy that refuses (or allows) the wrong hosts.
#   EGRESS_ALLOWLIST      comma-separated exact host names or *.suffix (same as the backend's)
#   EGRESS_ALLOWED_PORTS  space-separated destination ports, default 443
#   --print               print the translated lists and exit (tests, review)
set -eu

fail() {
    echo "egress-proxy: $*" >&2
    exit 1
}

run_dir=/run/ffcore-egress
host_re='^(\*\.)?([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)*[a-z0-9]([a-z0-9-]*[a-z0-9])?$'

domains=$(printf '%s\n' "${EGRESS_ALLOWLIST:-}" | tr ',' '\n' | while IFS= read -r entry; do
    host=$(printf '%s' "$entry" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | tr 'A-Z' 'a-z')
    [ -n "$host" ] || continue
    if ! printf '%s\n' "$host" | grep -Eq "$host_re"; then
        echo "egress-proxy: '$host' in EGRESS_ALLOWLIST is not a host name or *.suffix" >&2
        echo "!invalid"
        continue
    fi
    # Squid's dstdomain: a leading dot matches the domain and every subdomain.
    printf '%s\n' "$host" | sed 's/^\*\./\./'
done)
case "$domains" in
    *'!invalid'*) fail "EGRESS_ALLOWLIST has a malformed entry (no scheme, port, path or inner *)" ;;
esac
[ -n "$domains" ] || fail "EGRESS_ALLOWLIST is empty; the egress profile needs the provider hosts"

ports=${EGRESS_ALLOWED_PORTS:-443}
for port in $ports; do
    printf '%s\n' "$port" | grep -Eq '^[0-9]{1,5}$' || fail "EGRESS_ALLOWED_PORTS: '$port' is not a port"
done

if [ "${1:-}" = "--print" ]; then
    printf '%s\n--- ports ---\n' "$domains"
    printf '%s\n' $ports
    exit 0
fi

mkdir -p "$run_dir"
chown proxy "$run_dir" 2>/dev/null || true
printf '%s\n' "$domains" > "$run_dir/allowlist.txt"
printf '%s\n' $ports > "$run_dir/ports.txt"
echo "egress-proxy: $(wc -l < "$run_dir/allowlist.txt") allowlisted domains, ports: $ports"
# Squid opens its logs as cache_effective_user (proxy), not root: let it reopen the
# container's stdout/stderr pipes (the log goes to `docker logs`, never to a file).
chmod 0666 /proc/self/fd/1 /proc/self/fd/2 2>/dev/null || chmod 0666 "$(readlink -f /proc/self/fd/1)" "$(readlink -f /proc/self/fd/2)"
exec squid -N -f /etc/squid/ffcore/squid.conf
