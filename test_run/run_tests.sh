#!/bin/bash
#
# TASK Test Runner
# Executes tests defined in test_definitions.conf
#
# Usage: ./run_tests.sh [options] [test_name...]
#   -l, --list     List available tests
#   -c, --clean    Clean up test outputs after running
#   -v, --verbose  Show detailed output
#   -t, --timeout  Override default timeout (seconds)
#   -h, --help     Show this help message
#
# Examples:
#   ./run_tests.sh                    # Run all tests
#   ./run_tests.sh eq_iter01          # Run specific test
#   ./run_tests.sh eq_iter01 tx_std   # Run multiple tests
#   ./run_tests.sh -l                 # List available tests
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_DIR="$(dirname "$SCRIPT_DIR")"
TEST_OUTPUT_DIR="$SCRIPT_DIR/test_output"
TEST_DEF_FILE="$SCRIPT_DIR/test_definitions.conf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Options
CLEAN=0
VERBOSE=0
TIMEOUT_OVERRIDE=""
LIST_ONLY=0
SELECTED_TESTS=()

# Counters
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

# Track completed tests for dependency resolution
declare -A COMPLETED_TESTS

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--clean)
            CLEAN=1
            shift
            ;;
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -t|--timeout)
            TIMEOUT_OVERRIDE="$2"
            shift 2
            ;;
        -l|--list)
            LIST_ONLY=1
            shift
            ;;
        -h|--help)
            echo "TASK Test Runner"
            echo ""
            echo "Usage: $0 [options] [test_name...]"
            echo ""
            echo "Options:"
            echo "  -l, --list     List available tests"
            echo "  -c, --clean    Clean up test outputs after running"
            echo "  -v, --verbose  Show detailed output"
            echo "  -t, --timeout  Override default timeout (seconds)"
            echo "  -h, --help     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests"
            echo "  $0 eq_iter01          # Run specific test"
            echo "  $0 eq_iter01 tx_std   # Run multiple tests"
            echo "  $0 -l                 # List available tests"
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            SELECTED_TESTS+=("$1")
            shift
            ;;
    esac
done

# Check if test definition file exists
if [[ ! -f "$TEST_DEF_FILE" ]]; then
    echo -e "${RED}Error: Test definition file not found: $TEST_DEF_FILE${NC}"
    exit 1
fi

# Function to get module binary path
get_binary() {
    local module="$1"
    case "$module" in
        eq) echo "$TASK_DIR/eq/eq" ;;
        tr) echo "$TASK_DIR/tr/tr2" ;;
        ti) echo "$TASK_DIR/ti/ti" ;;
        fp) echo "$TASK_DIR/fp/fp" ;;
        wr) echo "$TASK_DIR/wr/wr" ;;
        wrx) echo "$TASK_DIR/wrx/wrx" ;;
        tx) echo "$TASK_DIR/tx/tx2" ;;
        tot) echo "$TASK_DIR/tot/tot" ;;
        # Phase L-6: python dispatch is not a file on disk but a marker so
        # list_tests() does not flag python-typed rows as "not built".
        python) echo "PYTHON_DISPATCH" ;;
        *) echo "" ;;
    esac
}

# Function to parse test definition
parse_test_def() {
    local line="$1"
    # Remove comments and trim
    line="${line%%#*}"
    line="$(echo "$line" | xargs)"

    if [[ -z "$line" ]]; then
        return 1
    fi

    IFS=':' read -r TEST_NAME MODULE INPUT_FILE DEPENDS TIMEOUT DESCRIPTION <<< "$line"
    return 0
}

# Function to list all tests
list_tests() {
    echo "========================================"
    echo "  Available Tests"
    echo "========================================"
    echo ""
    printf "%-15s %-6s %-10s %s\n" "TEST_NAME" "MODULE" "TIMEOUT" "DESCRIPTION"
    printf "%-15s %-6s %-10s %s\n" "---------" "------" "-------" "-----------"

    while IFS= read -r line; do
        if parse_test_def "$line"; then
            local binary=$(get_binary "$MODULE")
            local status=""
            # PYTHON_DISPATCH is the L-6 marker: it is not a path on disk,
            # so skip the -x check for those rows.
            if [[ "$binary" != "PYTHON_DISPATCH" && ! -x "$binary" ]]; then
                status=" (not built)"
            fi
            printf "%-15s %-6s %-10s %s%s\n" "$TEST_NAME" "$MODULE" "${TIMEOUT}s" "$DESCRIPTION" "$status"
        fi
    done < "$TEST_DEF_FILE"
    echo ""
}

# Function to check if test should run
should_run_test() {
    local test_name="$1"

    # If no tests specified, run all
    if [[ ${#SELECTED_TESTS[@]} -eq 0 ]]; then
        return 0
    fi

    # Check if test is in selected list
    for selected in "${SELECTED_TESTS[@]}"; do
        if [[ "$selected" == "$test_name" ]]; then
            return 0
        fi
    done

    return 1
}

# Function to check and run dependencies
run_dependencies() {
    local depends="$1"

    if [[ "$depends" == "none" || -z "$depends" ]]; then
        return 0
    fi

    IFS=',' read -ra DEP_ARRAY <<< "$depends"
    for dep in "${DEP_ARRAY[@]}"; do
        dep="$(echo "$dep" | xargs)"  # trim whitespace

        # Check if dependency already completed
        if [[ "${COMPLETED_TESTS[$dep]}" == "1" ]]; then
            continue
        fi

        # Find and run dependency
        while IFS= read -r line; do
            if parse_test_def "$line"; then
                if [[ "$TEST_NAME" == "$dep" ]]; then
                    echo -e "  ${CYAN}Running dependency: $dep${NC}"
                    run_single_test "$TEST_NAME" "$MODULE" "$INPUT_FILE" "$DEPENDS" "$TIMEOUT" "$DESCRIPTION"
                    break
                fi
            fi
        done < "$TEST_DEF_FILE"

        # Check if dependency succeeded
        if [[ "${COMPLETED_TESTS[$dep]}" != "1" ]]; then
            echo -e "  ${RED}Dependency failed: $dep${NC}"
            return 1
        fi
    done

    return 0
}

# Function to run a single test
run_single_test() {
    local test_name="$1"
    local module="$2"
    # For MODULE=python the 3rd column is reinterpreted as a shell command
    # line (see test_definitions.conf "Phase L-6" section).
    local input_file="$3"
    local depends="$4"
    local timeout="$5"
    local description="$6"

    # Skip if already completed
    if [[ "${COMPLETED_TESTS[$test_name]}" == "1" ]]; then
        return 0
    fi

    TOTAL=$((TOTAL + 1))

    # Override timeout if specified
    if [[ -n "$TIMEOUT_OVERRIDE" ]]; then
        timeout="$TIMEOUT_OVERRIDE"
    fi

    # ---------------------------------------------------------------
    # Phase L-6: python / C-ABI dispatch.
    #
    # MODULE=python reinterprets $input_file as a shell command executed
    # from $TASK_DIR with PYTHONPATH=python. Output is captured to
    # $TEST_OUTPUT_DIR/$test_name/output.log just like Fortran tests.
    # Exits early so the Fortran path below stays untouched.
    # ---------------------------------------------------------------
    if [[ "$module" == "python" ]]; then
        echo -n "[$TOTAL] $test_name ($description) ... "
        local test_dir="$TEST_OUTPUT_DIR/$test_name"
        mkdir -p "$test_dir"
        local log_file="$test_dir/output.log"
        local cmd="$input_file"
        if [[ $VERBOSE -eq 1 ]]; then
            echo ""
            ( cd "$TASK_DIR" && PYTHONPATH=python timeout "$timeout" sh -c "$cmd" ) 2>&1 | tee "$log_file"
            local exit_code=${PIPESTATUS[0]}
        else
            ( cd "$TASK_DIR" && PYTHONPATH=python timeout "$timeout" sh -c "$cmd" ) > "$log_file" 2>&1
            local exit_code=$?
        fi
        if [[ $exit_code -eq 124 ]]; then
            echo -e "${YELLOW}TIMEOUT${NC} (exceeded ${timeout}s)"
            FAILED=$((FAILED + 1))
        elif [[ $exit_code -eq 0 ]]; then
            echo -e "${GREEN}PASS${NC}"
            PASSED=$((PASSED + 1))
            COMPLETED_TESTS[$test_name]=1
        else
            echo -e "${RED}FAIL${NC} (exit code: $exit_code)"
            FAILED=$((FAILED + 1))
            if [[ $VERBOSE -eq 1 ]]; then
                echo "  Last 10 lines of log:"
                tail -10 "$log_file" | sed 's/^/    /'
            fi
        fi
        return 0
    fi

    local binary=$(get_binary "$module")
    local module_dir="$TASK_DIR/$module"

    # Handle @inputs prefix for local test inputs
    local full_input_path
    if [[ "$input_file" == @* ]]; then
        full_input_path="$SCRIPT_DIR/${input_file#@}"
    else
        full_input_path="$module_dir/$input_file"
    fi

    echo -n "[$TOTAL] $test_name ($description) ... "

    # Check if binary exists
    if [[ ! -x "$binary" ]]; then
        echo -e "${YELLOW}SKIP${NC} (module not built)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Check if input file exists
    if [[ ! -f "$full_input_path" ]]; then
        echo -e "${YELLOW}SKIP${NC} (input file not found: $full_input_path)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Run dependencies first
    if ! run_dependencies "$depends"; then
        echo -e "${YELLOW}SKIP${NC} (dependency failed)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Create test output directory
    local test_dir="$TEST_OUTPUT_DIR/$test_name"
    mkdir -p "$test_dir"

    # Invalidate this case's own outputs BEFORE anything is staged into the
    # directory. Two reasons, and the ordering matters for both:
    #
    #  - <module>_regress.dat is written mid-calculation (eq/eqcalq.f90:77),
    #    not at exit, so "the file exists" is only a success signal if it
    #    cannot be a previous run's file. Without this, a run that exits 0
    #    without reaching the dumper inherits the stale dump, the regression
    #    check compares THAT against the baseline, and the case reports PASS
    #    having computed nothing.
    #  - eqdata.* / *.gs are what a DEPENDENT consumes (copied from
    #    $dep_dir below). A case that fails to regenerate them would
    #    otherwise leave the previous invocation's files in place and let the
    #    dependent run green against stale input.
    #
    # This must run BEFORE the dependency copy (further down) and before the
    # tot-module input staging, or it would delete the very files those steps
    # just put here. test_dir persists across runs -- it is only removed
    # under --clean, and only after every case -- and regen-baselines.yml
    # invokes this script once per fixture in a fresh process, so
    # COMPLETED_TESTS is empty each time and dependencies are genuinely
    # re-run into a directory that already has last iteration's output.
    if [[ -n "$module" ]]; then
        rm -f "$test_dir/${module}_regress.dat"
        # One `eqdata*` glob, not eqdata.* plus eqdata-*: eq/eqinit.f90:100
        # defaults KNAMEQ to the bare name `eqdata`, which neither of the
        # two narrower patterns matches.
        rm -f "$test_dir"/eqdata* "$test_dir"/*.gs
    fi

    # Copy module-specific parameter files
    case "$module" in
        tx)
            # TX requires txparm file in working directory
            if [[ -f "$TASK_DIR/tx/in/txparm.std" ]]; then
                cp "$TASK_DIR/tx/in/txparm.std" "$test_dir/txparm"
            fi
            ;;
        ti)
            # TI's adf11 reader hard-codes ../adpost/ADPOST-DATA. The test
            # cwd is test_output/$test_name, so we expose ../adpost via a
            # one-shot symlink at test_output/adpost -> $TASK_DIR/adpost.
            # Same trick lets ./ADF11-bin.data resolve when present.
            if [[ ! -e "$TEST_OUTPUT_DIR/adpost" ]]; then
                ln -s "$TASK_DIR/adpost" "$TEST_OUTPUT_DIR/adpost" 2>/dev/null || true
            fi
            # Optional: expose ADF11-bin.data if it exists.
            #
            # Search order:
            #   1. test_run/fixtures/ADF11-bin.data  -- the synthetic
            #      "dummy" file generated by scripts/gen-dummy-adf11
            #      (committed; ~400 KB; structurally valid but not
            #      physically meaningful -- sufficient for equivalence
            #      regression tests).
            #   2. $TASK_DIR/adpost/ADF11-bin.data   -- real ADAS data
            #      installed by the user (licensed, not in the repo).
            #   3. $TASK_DIR/open-adas/adf11/ADF11-bin.data -- alt path.
            # Without any of these, ti_ar / ti_w fail cleanly via
            # tiprep's IERR guard.
            for adf11_src in \
                "$SCRIPT_DIR/fixtures/ADF11-bin.data" \
                "$TASK_DIR/adpost/ADF11-bin.data" \
                "$TASK_DIR/open-adas/adf11/ADF11-bin.data"; do
                if [[ -f "$adf11_src" ]]; then
                    ln -sf "$adf11_src" "$test_dir/ADF11-bin.data" 2>/dev/null || true
                    break
                fi
            done
            ;;
    esac

    # Copy dependency outputs if needed
    if [[ "$depends" != "none" && -n "$depends" ]]; then
        IFS=',' read -ra DEP_ARRAY <<< "$depends"
        for dep in "${DEP_ARRAY[@]}"; do
            dep="$(echo "$dep" | xargs)"
            local dep_dir="$TEST_OUTPUT_DIR/$dep"
            if [[ -d "$dep_dir" ]]; then
                # Copy output files (eqdata.*, etc.)
                cp "$dep_dir"/eqdata* "$test_dir/" 2>/dev/null || true
                cp "$dep_dir"/*.gs "$test_dir/" 2>/dev/null || true
            fi
        done
    fi

    # Run the test
    cd "$test_dir"
    local log_file="$test_dir/output.log"

    # For TR/FP/TI/WR/WRX/EQ/TOT modules, enable regression dump (env-guarded inside the dumper).
    local mod_env=()
    case "$module" in
        tr) mod_env=(env TR_REGRESS_DUMP=1) ;;
        fp) mod_env=(env FP_REGRESS_DUMP=1) ;;
        ti) mod_env=(env TI_REGRESS_DUMP=1) ;;
        wr) mod_env=(env WR_REGRESS_DUMP=1) ;;
        wrx) mod_env=(env WRX_REGRESS_DUMP=1) ;;
        eq) mod_env=(env EQ_REGRESS_DUMP=1) ;;
        tot)
            mod_env=(env TOT_REGRESS_DUMP=1)
            cp "$SCRIPT_DIR/inputs/eqdata"* "$test_dir/" 2>/dev/null || true
            cp "$SCRIPT_DIR/inputs/${test_name}.eqparm" "$test_dir/eqparm" 2>/dev/null || true
            cp "$SCRIPT_DIR/inputs/${test_name}.trparm" "$test_dir/trparm" 2>/dev/null || true
            ;;
    esac

    # For ti, the original .in files (committed in PR #6 / 0927fca1) do
    # not include the GSAF prologue lines that timain.f90's GSOPEN call
    # demands at startup. Prepend the prologue at run-time so we can
    # exercise the unmodified .in file (preserving the canonical
    # reference data the user expects). Other modules pass through
    # unchanged.
    local stdin_provider=""
    case "$module" in
        ti)
            stdin_provider="$test_dir/.ti_stdin_with_prologue"
            {
                echo "0"
                echo "f"
                echo "${test_name}.gs"
                echo "c"
                cat "$full_input_path"
            } > "$stdin_provider"
            ;;
        *)
            stdin_provider="$full_input_path"
            ;;
    esac

    # Timestamp reference for the post-run freshness check, written HERE --
    # after every staging step (the dependency copy and the tot input copy
    # above), immediately before the binary. Written earlier, as it first
    # was, it accomplished nothing: `cp` without -p stamps the destination
    # with the current time, so every staged file came out NEWER than the
    # sentinel and satisfied the check the sentinel exists to defeat.
    if [[ -n "$module" ]]; then
        : > "$test_dir/.pre_run"
    fi

    if [[ $VERBOSE -eq 1 ]]; then
        echo ""
        "${mod_env[@]}" timeout "$timeout" "$binary" < "$stdin_provider" 2>&1 | tee "$log_file"
        local exit_code=${PIPESTATUS[0]}
    else
        "${mod_env[@]}" timeout "$timeout" "$binary" < "$stdin_provider" > "$log_file" 2>&1
        local exit_code=$?
    fi

    cd "$SCRIPT_DIR"

    # Check result. "CLOSED" is the historical success indicator, but it is
    # emitted by GSAF's GSCLOS -- which is NOT in this repo. On a
    # graphics-free build (make.header with an empty GFLIBS, i.e. every CI
    # build) the module Makefiles link <mod>_static_stubs.o instead, whose
    # GSCLOS is an empty subroutine (eq/eq_static_stubs.f90:227-228, and
    # identically in tr/ and tot/). No log then contains "CLOSED", the
    # `exit_code -eq 0` branch below reports FAIL (no CLOSED message), and
    # COMPLETED_TESTS is never set -- so every dependent case is skipped as
    # "dependency failed". That made this script unusable on any
    # graphics-free build; the only reason it went unnoticed is that
    # python-tests.yml invokes the binaries directly and never calls it.
    #
    # So accept a second, equivalent signal: a clean exit that produced the
    # regression dump the module was asked for. That artefact is the actual
    # object of these runs, and REGRESS_DUMP is enabled for exactly the
    # modules checked below.
    local dump_produced=0
    if [[ -n "$module" && -s "$test_dir/${module}_regress.dat" ]]; then
        dump_produced=1
    fi
    if [[ $exit_code -eq 124 ]]; then
        echo -e "${YELLOW}TIMEOUT${NC} (exceeded ${timeout}s)"
        FAILED=$((FAILED + 1))
    elif grep -q "CLOSED" "$log_file" 2>/dev/null \
         || { [[ $exit_code -eq 0 ]] && [[ $dump_produced -eq 1 ]]; }; then
        # Calculation completed successfully.
        # For TR module, also verify numerical metrics against baseline.
        # check_regression.sh distinguishes its failures: 1 = metrics drift,
        # 2 = dump missing/malformed, 3 = baseline missing, 4 = bad prefix.
        # Collapsing them into one boolean reported "REGRESSION (metrics
        # drift)" for a run that produced NO metrics at all -- and then, per
        # the COMPLETED_TESTS rule below, let its dependents proceed on
        # whatever stale eqdata was lying around. Only 1 means "ran, produced
        # artefacts, disagrees with the baseline"; 2 and 3 mean the run or the
        # repo is broken.
        local reg_rc=0
        if [[ "$module" == "tr" || "$module" == "fp" || "$module" == "ti" || "$module" == "wr" || "$module" == "wrx" || "$module" == "eq" || "$module" == "tot" ]]; then
            "$SCRIPT_DIR/scripts/check_regression.sh" \
                    "$test_name" "$test_dir" "$SCRIPT_DIR/baselines" "1e-10" \
                    > "$test_dir/regression.log" 2>&1 || reg_rc=$?
        fi
        if [[ $reg_rc -eq 3 ]]; then
            # Baseline missing. The RUN succeeded -- check_regression.sh only
            # reaches its exit 3 after finding the dump and writing
            # metrics.json -- so the artefacts a dependent needs do exist.
            # Marking it incomplete would skip the dependent, leave its output
            # directory uncreated, and break precisely the BOOTSTRAP case a
            # regeneration workflow exists for: a brand-new eq_* case has no
            # baseline yet by definition, and its tr_* dependent would never
            # run to produce one.
            echo -e "${RED}FAIL${NC} (no baseline under $SCRIPT_DIR/baselines/$test_name; see $test_dir/regression.log)"
            FAILED=$((FAILED + 1))
            # ...but only if the artefacts a DEPENDENT consumes are actually
            # there. exit 3 proves the DUMP exists, which is weaker: the dump
            # is written at the tail of EQCALQ (the menu's `r`), while
            # eqdata.* comes from EQSAVE (the menu's `s`), later. A bootstrap
            # script that reaches `r` but not `s` would otherwise be marked
            # complete and let its dependent run with no equilibrium file at
            # all -- and under regen-baselines.yml that is not even red: the
            # run_tests.sh call is `|| true`'d and the dump/`jq` gates both
            # pass, so a metrics.json computed without an equilibrium would be
            # uploaded as the artifact intended to BECOME the baseline.
            # `-newer .pre_run` and `-type f`: the gate must mean "THIS run
            # wrote an equilibrium", not "an eqdata file is present". Files
            # staged before the binary (a dependency's blob at the copy
            # below, or the tot input staging) would otherwise
            # satisfy it, and in an eq_A -> eq_B -> tr_C chain an eq_B that
            # reached `r` but not `s` would be marked complete on eq_A's
            # blob. `-type f` also rejects a directory named eqdata*.
            if [[ -n "$(find "$test_dir" -maxdepth 1 -type f -name 'eqdata*' \
                             -newer "$test_dir/.pre_run" -print -quit 2>/dev/null)" ]]; then
                COMPLETED_TESTS[$test_name]=1
            else
                echo -e "         ${YELLOW}(and no eqdata produced -- dependents will be skipped)${NC}"
            fi
        elif [[ $reg_rc -ge 2 ]]; then
            local reason
            case $reg_rc in
                2) reason="regression dump missing or malformed" ;;
                *) reason="check_regression.sh exit $reg_rc" ;;
            esac
            echo -e "${RED}FAIL${NC} ($reason; see $test_dir/regression.log)"
            FAILED=$((FAILED + 1))
            # NOT marked complete: no usable dump means no artefacts a
            # dependent can consume, so letting one proceed would run it
            # against a previous invocation's leftovers.
        elif [[ $reg_rc -eq 1 ]]; then
            echo -e "${RED}REGRESSION${NC} (metrics drift; see $test_dir/regression.log)"
            FAILED=$((FAILED + 1))
            # Still mark it complete FOR DEPENDENTS. COMPLETED_TESTS answers
            # "did this case produce output a dependent can consume?", which
            # is a different question from "did it match its baseline". The
            # run reached GSCLOS/produced its dump and wrote its eqdata; a
            # metrics drift says the BASELINE is out of date, not that the
            # artefacts are unusable.
            #
            # Conflating the two made a drifted eq_iter01 skip tr_iter01 as
            # "dependency failed", so tr_iter01's output directory was never
            # created -- which is fatal precisely for a baseline-REGENERATION
            # run, where every case is expected to drift. Measured on the
            # first-ever run of regen-baselines.yml (30514627136): eq_iter01
            # and eq_tst2 REGRESSED as expected, and tr_iter01/tr_tst2 were
            # then skipped and produced nothing.
            #
            # The verdict is unchanged -- FAILED is still incremented, so the
            # script still exits nonzero and a drift never reads as a pass.
            COMPLETED_TESTS[$test_name]=1
        elif [[ $exit_code -ne 0 ]]; then
            echo -e "${GREEN}PASS${NC} (warning: exit code $exit_code)"
            PASSED=$((PASSED + 1))
            COMPLETED_TESTS[$test_name]=1
        else
            echo -e "${GREEN}PASS${NC}"
            PASSED=$((PASSED + 1))
            COMPLETED_TESTS[$test_name]=1
        fi
    elif [[ $exit_code -eq 0 ]]; then
        # Clean exit, but neither "CLOSED" nor a regression dump: the run
        # went nowhere useful. Name both missing signals -- "no CLOSED
        # message" alone sent the graphics-free case chasing a red herring.
        #
        # But only name the dump for modules that HAVE a dumper. `tx` has
        # no entry in the mod_env case above, so no *_REGRESS_DUMP is ever
        # enabled for it -- reporting "no tx_regress.dat" would name an
        # artefact nobody asked for. tx_std therefore still cannot pass on
        # a graphics-free build; that needs a tx dumper, not a message fix.
        if [[ ${#mod_env[@]} -gt 0 ]]; then
            echo -e "${RED}FAIL${NC} (no CLOSED message and no ${module}_regress.dat)"
        else
            echo -e "${RED}FAIL${NC} (no CLOSED message; ${module} has no regression dumper)"
        fi
        FAILED=$((FAILED + 1))
        if [[ $VERBOSE -eq 1 ]]; then
            echo "  Last 10 lines of log:"
            tail -10 "$log_file" | sed 's/^/    /'
        fi
    else
        echo -e "${RED}FAIL${NC} (exit code: $exit_code)"
        FAILED=$((FAILED + 1))
        if [[ $VERBOSE -eq 1 ]]; then
            echo "  Last 10 lines of log:"
            tail -10 "$log_file" | sed 's/^/    /'
        fi
    fi
}

# ============================================================
# Main Execution
# ============================================================

# List mode
if [[ $LIST_ONLY -eq 1 ]]; then
    list_tests
    exit 0
fi

echo "========================================"
echo "  TASK Test Runner"
echo "========================================"
echo "Date: $(date)"
if [[ ${#SELECTED_TESTS[@]} -gt 0 ]]; then
    echo "Selected tests: ${SELECTED_TESTS[*]}"
else
    echo "Running: All tests"
fi
echo ""

# Create output directory
mkdir -p "$TEST_OUTPUT_DIR"

# Run tests
while IFS= read -r line; do
    if parse_test_def "$line"; then
        if should_run_test "$TEST_NAME"; then
            run_single_test "$TEST_NAME" "$MODULE" "$INPUT_FILE" "$DEPENDS" "$TIMEOUT" "$DESCRIPTION"
        fi
    fi
done < "$TEST_DEF_FILE"

# Summary
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo "Total:   $TOTAL"
echo -e "Passed:  ${GREEN}$PASSED${NC}"
echo -e "Failed:  ${RED}$FAILED${NC}"
echo -e "Skipped: ${YELLOW}$SKIPPED${NC}"
echo ""

if [[ $FAILED -eq 0 && $TOTAL -gt 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
elif [[ $TOTAL -eq 0 ]]; then
    echo -e "${YELLOW}No tests were run.${NC}"
else
    echo -e "${RED}Some tests failed. Check $TEST_OUTPUT_DIR for logs.${NC}"
fi

# Cleanup if requested
if [[ $CLEAN -eq 1 ]]; then
    echo ""
    echo "Cleaning up test outputs..."
    rm -rf "$TEST_OUTPUT_DIR"
    echo "Done."
fi

# Return appropriate exit code
if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
