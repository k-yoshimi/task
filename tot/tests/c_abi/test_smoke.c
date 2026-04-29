/*
 * Phase L-3 C ABI smoke test for the tot orchestrator's set_param
 * dispatcher contracts.
 *
 * tot_set_param (and tot_set_param_str) dispatch to per-module
 * registries; this driver pins the dispatcher's pre-routing rejection
 * paths, which by design hold regardless of whether tot is initialized
 * or not. The init -> run -> get_state -> finalize happy path is
 * covered by test_full_cycle.c (Phase L-6); the pre-init / unknown-
 * namespace / double-finalize negative contracts are covered by
 * test_negative.c.
 *
 * Originally (Phase L-3 / L-5) this driver also asserted that the
 * lifecycle entry points returned TOT_ERR_NOT_IMPL while they were
 * stubs. With L-6 those stubs were replaced by real fan-out, so the
 * NOT_IMPL assertions were removed; keeping them as TOT_OK assertions
 * would just duplicate test_full_cycle.
 */
#include <stdio.h>
#include "tot_api.h"

static int expect(const char *name, int rc, int expected) {
    if (rc == expected) {
        printf("OK  %-28s returned %d\n", name, rc);
        return 0;
    }
    fprintf(stderr,
            "FAIL %s returned %d, expected %d\n",
            name, rc, expected);
    return 1;
}

int main(void) {
    int failures = 0;

    /* L-3 dispatcher: a bare name (no "<ns>:" prefix) is rejected. */
    failures += expect("set_param no-prefix",
                       tot_set_param("RR", 6.2),
                       TOT_ERR_INVALID);

    /* Unknown namespace is rejected. */
    failures += expect("set_param bad-ns",
                       tot_set_param("zz:RR", 6.2),
                       TOT_ERR_INVALID);

    /* Prefix-only (no bare name) is rejected. */
    failures += expect("set_param prefix-only",
                       tot_set_param("tr:", 0.0),
                       TOT_ERR_INVALID);

    /* String dispatch: same prefix rules, no state required to reject. */
    failures += expect("set_param_str no-prefix",
                       tot_set_param_str("KNAMEQ", "x"),
                       TOT_ERR_INVALID);
    failures += expect("set_param_str bad-ns",
                       tot_set_param_str("zz:KNAMEQ", "x"),
                       TOT_ERR_INVALID);

    if (failures != 0) {
        fprintf(stderr, "%d assertion(s) failed\n", failures);
        return 1;
    }
    printf("Phase L-3 tot smoke OK: dispatcher error paths verified\n");
    return 0;
}
