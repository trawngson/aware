# The native env exists only to run the unit tests (routing, LLM replies) on
# the Mac. Building it compiles src/ with the Mac's compiler, which has no
# Arduino.h, so stop early with a clear message instead.
Import("env")  # noqa: F821  (provided by PlatformIO)

if (
    "__test" not in COMMAND_LINE_TARGETS  # noqa: F821
    and not env.IsIntegrationDump()  # noqa: F821
    and not env.IsCleanTarget()  # noqa: F821
):
    print(
        "\nThe native env only runs the unit tests; it can't build the "
        "firmware.\n"
        "  Board firmware:     esp32s3cam → General → Build\n"
        "  Wokwi simulator:    sim → General → Build\n"
        "  Unit tests:         native → Advanced → Test\n"
    )
    env.Exit(1)  # noqa: F821
