# KRT-112 inspector crash and fast-suite recovery

Owner-authorized repair, 27 October 2026, following the KRT-111 implementation.
[KRT-112](https://linear.app/projektkraken/issue/KRT-112/fix-inspector-resize-crash-and-restore-ci-fast-verification)
records the verified repair. The owner requested a development-branch checkpoint
on 27 October; its commit hash and delivery status are recorded in Linear after
commit. This batch preserves the existing KRT-111 implementation and does not
push or replace a personal world.

## Reproduced causes and repairs

The single Entity case of
`test_connections_stay_one_line_at_narrow_and_wide_widths` reproduced a Windows
access violation at `inspector.resize()`. It also crashed when run as part of
`test_connections_overview.py`, after the first three projection tests. The
Python fault stack stopped at that resize call. A disposable vectored-exception
probe captured native export frames including:

```text
QBoxLayout::setGeometry
QFormLayout::setGeometry
QLayoutPrivate::doResize
QWidget::resize
```

Disabling the tree delegate or the overview's minimum-height calculation did
not remove the fault. Disabling `EditorPresentation.reflow` did. The inspector
event filter synchronously moved Inject between the name and compact action
rows during a Resize/Show event, while Qt was traversing those layouts. The
repair coalesces reflow through an owned zero-delay timer, allowing native
geometry traversal to finish before rows change. Initial construction retains
its explicit reflow. Existing actions, theme roles, compact/wide routes and
draft state are preserved; no new visual variant is introduced.

The navigation, creation and imported production-workspace fixtures replaced QThread
with MagicMock. Real feature endpoints introduced by earlier work correctly
require an actual QThread for `moveToThread`. Those fixtures now mock only
`QThread.start`: they retain real, stopped thread objects and keep database
startup mocked. Production affinity checks are not weakened.

Calendar-loaded and attachment-loaded notifications now reach decorated Context
coordinator slots through explicit queued connections. A disposable runtime
trace identified the attachment lambda in `connection_manager.py:277` calling
`schedule_entity_refresh` on the worker thread, even though that lambda's
connection was queued. The QObject receiver supplies the required GUI affinity;
the attachment filter retains Entity-only refresh. A real-thread regression
opts into the repository's `real_qt_invoke` fixture contract and checks both
receiving threads and the ignored Event attachment case.

World settings refresh previously invoked a nonexistent zero-argument Qt
`DatabaseWorker.load_graph_data()` slot. The Python method's defaults do not
create a zero-argument metaobject signature. Refresh now uses the existing
DataCoordinator route, which builds the Graph's current filter/time request and
delivers it through existing queued infrastructure. No worker slot or new
choke-point responsibility is added.

## Latest application log

The first application fault file inspected was `logs/faults.28860.log`, from
27 October 2026 at 07:14 UTC (08:14 Europe/Berlin), session
`9e07a573-f611-40d5-9059-9ea864077372`. Its corresponding application log is
`logs/kraken.28860.log`.

It records world startup, the missing zero-argument Graph slot warning and an
access violation whose Python stack ends at `entry.py:212`, `app.exec()`. That
frame identifies the event loop, not the native faulting function. Earlier
sessions `20352` and `57336` also recorded wrong-thread timer warnings. The
repair addresses the independently reproduced layout fault and the concrete
slot/threading defects; the latest application log alone cannot prove that
its native fault was identical to the isolated resize failure.

A final log refresh found a newer fatal session, `logs/faults.27376.log`,
started at 07:17 UTC. It repeats the missing Graph slot warning and the
event-loop access-violation stack. The newest session, `23412`, started at
07:37 UTC and ended normally at 07:38:15 UTC (08:38:15 Europe/Berlin).
`faults.23412.log` records a session end with no fatal exception, missing
Graph slot or wrong-thread timer warning; `kraken.23412.log` records worker
cleanup. These are log observations, not an independently observed user task
or a replay of the fatal interaction.

OpenGL fallback warnings are retained as observations. They did not explain
the controlled resize failure: disabling only immediate reflow made that same
offscreen reproduction pass.

## Verification and retained evidence

- Connections and Wiki return files: **64 passed** after the initial repair.
- Creation regressions selected by `ci_fast`: **29 passed, 10 deselected**.
- Focus navigation and Context coordinator checks after the final fixture and
  attachment repair: **51 passed**.
- Inspector composition and secondary-action themes: **70 passed**. The
  disclosure fixture now supplies visible tags rather than attributes omitted
  from human Context by the existing KRT-109 decision. Theme-state tests send
  an explicit Leave event outside hover states, preventing stale offscreen
  pointer state while retaining exact rendered color, border and text checks.
- Presentation, Settings and Context coordinator checks: the original focused
  run passed 75 cases; the added real-thread check initially encountered the
  repository's mocked invocation fixture. With its explicit opt-in, that
  regression passed using a real worker thread.
- Final complete `ci_fast`: **2,721 passed, 3 skipped**, 4,518 deselected,
  3 deprecation warnings, **585.09 seconds**, process exit **0**. All 2,724
  selected cases completed without setup errors or native crashes.
- Repository-wide mypy passed for 532 source files. Help inspection and
  complexity, visual and test-inventory policies passed; reviewed complexity
  allowances are unchanged. Ruff, offline Help and strict Sphinx passed.

Run the complete gate with `QT_QPA_PLATFORM=offscreen`:

```text
python -X faulthandler -m pytest -m ci_fast -q --tb=short --show-capture=no -o faulthandler_timeout=90 --durations=10 --junitxml=artifacts/ci-fast-repair/ci-fast-final.xml
```

Ignored artifacts are retained under `artifacts/ci-fast-repair/`:
`repro-before.log`, `native-stack.txt`, discovery `ci-fast.log`/`ci-fast.xml`,
final `ci-fast-final.log`/`ci-fast-final.xml`, and
the disposable `app_probe.py`/`app_probe_timer.py` with per-run settings, generated Northwatch worlds,
runtime logs and `report.json` under `runtime/<run-id>/`. The probe uses real
DatabaseWorker/QThread startup and cycles Entity/Event selection, Connections,
window widths 760/1280 and fantasy/dark themes. Its initial 45-second attempt
reached startup and five steps before its watchdog expired; that is not a
completed probe. Run `f7171795` completed all eight theme/width/Entity-Event
steps and exited 0, with the remaining attachment timer warning. After tracing
and repairing that callback, run `ae540feb` completed startup and two
fantasy-theme Entity/Event steps at width 760 and exited 0. Its fault log
`faults.39792.log` contains no wrong-thread timer, missing Graph slot or access
violation; no `timer-stacks.txt` was produced. These are bounded offscreen
observations, not a replay of the author's exact failing interaction.

No personal world was opened by the probe and no artifact cleanup was performed.
Offscreen runtime execution is distinct from native Windows DPI acceptance and
human UX review. Existing KRT-111 human-review conditions remain open.
