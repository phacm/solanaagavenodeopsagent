# Local development stack (NO gate weight)

Everything runs under your uid (`dev_single_uid`), with a file anchor store, a file alert
sink and the host-read-only development rootfs. Per HLD §10.1 none of this counts toward
G1: real boundaries mean real uids, the real sandbox backend with a minimal rootfs, a real
retention-locked anchor store and the pinned runtime.

    ./deploy/dev/up.sh            # keys, dev bundle, configs under ./var/dev
    valops serve --config var/dev/ops.yaml all
    valops observerd --config var/dev/observerd.yaml   # plain HTTP, builtins only
