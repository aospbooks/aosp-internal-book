# Chapter 23: Window System

The Android window system is a multi-layered architecture that spans from native composition (SurfaceFlinger) through Java framework services (WindowManagerService) to a presentation library (WM Shell) that orchestrates animations and feature UIs. This chapter provides a comprehensive analysis of the window management layer -- the policy engine that sits between applications requesting screen real estate and the compositor that paints pixels to the display.

Chapter 13 (Graphics & Render Pipeline) covered how buffers flow from application through HWUI to SurfaceFlinger. This chapter covers the layer above that: how windows are created, tracked, organized into a hierarchy, animated through transitions, and managed across multiple displays and windowing modes. A companion three-part detailed report (referenced in section 23.11) provides a 100-section deep dive; this chapter provides the architectural foundation needed to read that report productively.

---

## 23.1 Window Management Architecture

### 23.1.1 Architectural Overview

The window management system is organized into four distinct layers, each with a clear separation of concerns:

```mermaid
graph TB
    subgraph "Application Layer"
        APP["App Process<br/>(ViewRootImpl + WindowManager)"]
    end

    subgraph "System Server — WM Core"
        WMS["WindowManagerService<br/>Policy Engine"]
        ATMS["ActivityTaskManagerService<br/>Task Lifecycle"]
        RWC["RootWindowContainer<br/>Hierarchy Root"]
        TC["TransitionController<br/>Transition Orchestration"]
        WOC["WindowOrganizerController<br/>Organizer Dispatch"]
    end

    subgraph "System Server — WM Shell"
        STO["ShellTaskOrganizer<br/>Task Surface Control"]
        TR["Transitions<br/>Animation Player"]
        SC["ShellController<br/>Feature Registry"]
    end

    subgraph "Native Layer"
        SF["SurfaceFlinger<br/>Compositor"]
        IF["InputFlinger<br/>Input Dispatch"]
    end

    APP -->|"IWindowSession<br/>(Binder)"| WMS
    WMS <-->|"Internal API"| ATMS
    ATMS --> RWC
    WMS --> TC
    TC -->|"TransitionInfo"| TR
    WOC -->|"TaskOrganizer<br/>callbacks"| STO

    WMS -->|"SurfaceControl.Transaction"| SF
    STO -->|"SurfaceControl.Transaction"| SF
    TR -->|"SurfaceControl.Transaction"| SF

    WMS -->|"InputWindowHandle"| IF
    IF -->|"InputChannel"| APP

    style WMS fill:#e1f5fe
    style TR fill:#f3e5f5
    style SF fill:#fff3e0
```

The key insight is that all three Java layers (App, WM Core, WM Shell) can issue `SurfaceControl.Transaction` commands directly to SurfaceFlinger. This is not a strict pipeline but a collaborative model: WM Core sets policy, Shell sets presentation, and both push surface operations to the compositor.

### 23.1.2 WindowManagerService

`WindowManagerService` (WMS) is the central policy engine of the window system. Located at:

```
frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java
```

At over 11,500 lines in the Android 17 tree, it is one of the largest classes in the Android framework. WMS extends `IWindowManager.Stub` and implements `Watchdog.Monitor` and `WindowManagerPolicy.WindowManagerFuncs`:

```java
public class WindowManagerService extends IWindowManager.Stub
        implements Watchdog.Monitor, WindowManagerPolicy.WindowManagerFuncs {
```

WMS is responsible for:

1. **Window lifecycle management** -- Adding, removing, and relaying out windows via `IWindowSession`
2. **Focus management** -- Determining which window receives input focus, with five update modes (`UPDATE_FOCUS_NORMAL`, `UPDATE_FOCUS_WILL_ASSIGN_LAYERS`, `UPDATE_FOCUS_PLACING_SURFACES`, `UPDATE_FOCUS_WILL_PLACE_SURFACES`, `UPDATE_FOCUS_REMOVING_FOCUS`)
3. **Policy enforcement** -- Window type permissions, secure content flags, overlay restrictions
4. **Surface synchronization** -- The global lock (`mGlobalLock`) that protects all window state, shared with `ActivityTaskManagerService`
5. **Display configuration** -- DPI overrides, forced scaling modes, display settings
6. **Animation coordination** -- Window animation scales, transition timeouts

Key constants define the operational boundaries:

```java
static final int WINDOW_FREEZE_TIMEOUT_DURATION = 2000;        // 2 seconds
static final int LAST_ANR_LIFETIME_DURATION_MSECS = 2 * 60 * 60 * 1000; // 2 hours
```

(The per-animation duration cap is `TransitionAnimation.MAX_ANIMATION_DURATION`, imported and applied in `WindowState.applyAnimationLocked()` via `restrictDuration()`, rather than a WMS field.)

WMS holds references to critical subsystem controllers:

- `mDisplayAreaPolicyProvider` -- Controls how `DisplayArea` hierarchies are constructed per display
- `mWindowTracing` / `mTransitionTracer` -- Debugging infrastructure
- `mConstants` -- Runtime-configurable parameters via `WindowManagerConstants`

### 23.1.3 The WindowContainer Hierarchy

The window system models all window-related objects as a tree of `WindowContainer` nodes. Every node maintains a parent reference, a list of children in z-order, and a 1:1 mapping to a `SurfaceControl` in the SurfaceFlinger layer tree.

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/WindowContainer.java` (over 3,800 lines)

```java
class WindowContainer<E extends WindowContainer> extends ConfigurationContainer<E>
        implements Comparable<WindowContainer>, Animatable {

    private WindowContainer<WindowContainer> mParent = null;
    protected final ArrayList<E> mChildren = new ArrayList<E>();
    protected SurfaceControl mSurfaceControl;
    protected final SurfaceAnimator mSurfaceAnimator;
    final TransitionController mTransitionController;
}
```

Key properties of `WindowContainer`:

- **Children are z-ordered**: The `mChildren` list is maintained in z-order, with the top-most child at the tail (highest index). The `POSITION_TOP` and `POSITION_BOTTOM` constants (`Integer.MAX_VALUE` and `Integer.MIN_VALUE`) enable explicit ordering.

- **Surface 1:1 mapping**: `mSurfaceControl` mirrors this node in the SurfaceFlinger layer tree. Every hierarchy change (reparent, reorder) produces a corresponding `SurfaceControl.Transaction`.

- **Animation via leash**: `mSurfaceAnimator` manages a separate `SurfaceControl` (the "leash") that is interposed between this node and its parent during animations. All children are reparented to the leash so animations can transform the entire subtree.

- **Sync state machine**: `mSyncState` tracks whether this container is participating in a BLAST sync group (`SYNC_STATE_NONE`, `SYNC_STATE_WAITING_FOR_DRAW`, `SYNC_STATE_READY`).

- **Configuration propagation**: Extends `ConfigurationContainer`, so configuration changes (rotation, density, windowing mode) cascade down the tree.

### 23.1.4 Complete Class Hierarchy

The following diagram shows the complete inheritance hierarchy from `WindowContainer` down to concrete leaf types:

```mermaid
classDiagram
    class ConfigurationContainer {
        +Configuration mRequestedOverrideConfiguration
        +Configuration mResolvedOverrideConfiguration
        +Configuration mFullConfiguration
        +onConfigurationChanged()
    }

    class WindowContainer {
        -WindowContainer mParent
        #ArrayList~E~ mChildren
        #SurfaceControl mSurfaceControl
        #SurfaceAnimator mSurfaceAnimator
        +TransitionController mTransitionController
        +BLASTSyncEngine.SyncGroup mSyncGroup
        +int mSyncState
        +addChild()
        +removeChild()
        +prepareSurfaces()
    }

    class DisplayArea {
        +int mFeatureId
        +addWindow()
        +findAreaForWindowType()
    }

    class RootDisplayArea {
        +DisplayAreaPolicy mPolicy
        +placeWindowTokens()
    }

    class DisplayContent {
        +int mDisplayId
        +InputMonitor mInputMonitor
        +InsetsStateController mInsetsStateController
        +ImeContainer mImeWindowsContainer
        +DisplayFrames mDisplayFrames
    }

    class RootWindowContainer {
        +ArrayList~DisplayContent~ mChildren
        +performSurfacePlacement()
        +updateFocusedWindowLocked()
    }

    class TaskDisplayArea {
        +ArrayList~Task~ mChildren
        +createRootTask()
    }

    class WindowToken {
        +IBinder token
        +int windowType
    }

    class ActivityRecord {
        +ActivityInfo info
        +State mState
        +Task task
    }

    class TaskFragment {
        +int mTaskFragmentOrganizerUid
    }

    class Task {
        +int mTaskId
        +int mUserId
        +Intent mIntent
    }

    class WindowState {
        +Session mSession
        +WindowManager.LayoutParams mAttrs
        +int mViewVisibility
        +WindowFrames mWindowFrames
    }

    ConfigurationContainer <|-- WindowContainer
    WindowContainer <|-- DisplayArea
    DisplayArea <|-- RootDisplayArea
    RootDisplayArea <|-- DisplayContent
    WindowContainer <|-- RootWindowContainer
    DisplayArea <|-- TaskDisplayArea
    WindowContainer <|-- WindowToken
    WindowToken <|-- ActivityRecord
    WindowContainer <|-- TaskFragment
    TaskFragment <|-- Task
    WindowContainer <|-- WindowState
```

The hierarchy from root to leaf for a typical display is:

```
RootWindowContainer
  └── DisplayContent (display 0)
        └── DisplayArea.Root
              ├── DisplayArea (HideDisplayCutout)
              │     ├── DisplayArea (OneHanded)
              │     │     ├── DisplayArea (Magnification)
              │     │     │     ├── TaskDisplayArea (DefaultTaskDisplayArea)
              │     │     │     │     ├── Task (root task)
              │     │     │     │     │     ├── Task (leaf task)
              │     │     │     │     │     │     ├── ActivityRecord
              │     │     │     │     │     │     │     └── WindowState (main window)
              │     │     │     │     │     │     │           └── WindowState (sub-window)
              │     │     │     │     │     │     └── ActivityRecord
              │     │     │     │     │     └── Task (leaf task)
              │     │     │     │     └── Task (root task - PiP)
              │     │     │     └── WindowToken (TYPE_WALLPAPER)
              │     │     │           └── WindowState (wallpaper)
              │     │     └── WindowToken (TYPE_STATUS_BAR)
              │     │           └── WindowState (status bar)
              │     └── DisplayArea (AppZoomOut)
              ├── ImeContainer
              │     └── WindowToken (TYPE_INPUT_METHOD)
              │           └── WindowState (IME)
              ├── WindowToken (TYPE_NAVIGATION_BAR)
              │     └── WindowState (nav bar)
              └── WindowToken (TYPE_NOTIFICATION_SHADE)
                    └── WindowState (shade)
```

### 23.1.5 WindowState

`WindowState` is the server-side representation of a single window. It extends `WindowContainer<WindowState>`, meaning its children are sub-windows (TYPE_APPLICATION_PANEL, TYPE_APPLICATION_MEDIA, etc.).

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/WindowState.java` (over 6,400 lines)

```java
class WindowState extends WindowContainer<WindowState>
        implements WindowManagerPolicy.WindowState,
                   InputTarget,
                   InsetsControlTarget {
```

WindowState implements three critical interfaces:

- `WindowManagerPolicy.WindowState` -- Policy queries about window attributes
- `InputTarget` -- Input dispatch targeting
- `InsetsControlTarget` -- Insets animation control

Key fields:

| Field | Type | Purpose |
|-------|------|---------|
| `mSession` | `Session` | Binder connection to the client process |
| `mAttrs` | `WindowManager.LayoutParams` | Window type, flags, soft input mode |
| `mViewVisibility` | `int` | Client-requested visibility (VISIBLE/INVISIBLE/GONE) |
| `mWindowFrames` | `WindowFrames` | Computed frame, display frame, content frame |
| `mRequestedWidth/Height` | `int` | Client's requested dimensions |
| `mGlobalScale` | `float` | Compatibility scaling factor |
| `mInsetsSourceProviders` | `SparseArray` | Insets this window provides to others |
| `mWinAnimator` | `WindowStateAnimator` | Legacy animation state |

### 23.1.6 DisplayContent

`DisplayContent` represents one logical display in the window hierarchy. It extends `RootDisplayArea`, which itself extends `DisplayArea.Dimmable`, which extends `DisplayArea`, which extends `WindowContainer`.

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/DisplayContent.java` (over 7,700 lines)

```java
class DisplayContent extends RootDisplayArea
        implements WindowManagerPolicy.DisplayContentInfo {

    final int mDisplayId;
    @Nullable String mCurrentUniqueDisplayId;
    private SurfaceControl mOverlayLayer;
    private SurfaceControl mInputOverlayLayer;
    private final ImeContainer mImeWindowsContainer;
    int mMinSizeOfResizeableTaskDp;
}
```

DisplayContent maintains several special surface layers:

- `mOverlayLayer` -- Always-on-top surfaces (strict mode flash, magnification overlay)
- `mInputOverlayLayer` -- Input-related overlay surfaces
- `mPointerEventDispatcherOverlayLayer` -- Receives all pointer input on the display
- `mA11yOverlayLayer` -- Accessibility overlay surfaces

Each DisplayContent creates its own `InsetsStateController` to manage system bar insets, its own `InputMonitor` for input dispatch, and its own `DisplayFrames` for layout computation.

### 23.1.7 RootWindowContainer

`RootWindowContainer` is the absolute root of the window hierarchy. It is a direct child of `WindowManagerService` and contains all `DisplayContent` instances.

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java`

Its primary responsibilities are:

- `performSurfacePlacement()` -- The main layout pass that computes window positions and pushes surface transactions
- `updateFocusedWindowLocked()` -- Determines the globally focused window across all displays
- Managing display addition/removal as displays connect/disconnect
- Routing intents and activities to appropriate displays

### 23.1.8 The Surface Placement Cycle

Window layout follows a cyclic pattern driven by `RootWindowContainer.performSurfacePlacement()`:

```mermaid
sequenceDiagram
    participant WMS as WindowManagerService
    participant RWC as RootWindowContainer
    participant DC as DisplayContent
    participant WS as WindowState
    participant SF as SurfaceFlinger

    WMS->>RWC: performSurfacePlacement()
    RWC->>DC: performLayout()
    DC->>WS: computeFrames()
    WS-->>DC: WindowFrames updated

    RWC->>DC: prepareSurfaces()
    DC->>WS: prepareSurfaces()
    Note over WS: Set position, size, visibility<br/>on pending transaction

    RWC->>SF: SurfaceControl.Transaction.apply()
    Note over SF: Atomic commit of all<br/>surface changes
```

The `LAYOUT_REPEAT_THRESHOLD` (4) limits how many times the layout pass can re-run within a single placement cycle to prevent infinite loops when layout changes trigger further layout changes.

### 23.1.9 WMS Internal Data Structures

WindowManagerService maintains several critical collections that enable fast window lookup and lifecycle management:

```java
// Active client sessions (one per connected process)
final ArraySet<Session> mSessions = new ArraySet<>();

// Fast lookup: IWindow binder token → WindowState
final HashMap<IBinder, WindowState> mWindowMap = new HashMap<>();

// Fast lookup: InputWindowHandle token → WindowState
final HashMap<IBinder, WindowState> mInputToWindowMap = new HashMap<>();

// Windows currently being resized (need client notification after transaction)
final ArrayList<WindowState> mResizingWindows = new ArrayList<>();

// Windows with frame changes pending
final ArrayList<WindowState> mFrameChangingWindows = new ArrayList<>();

// Windows whose surfaces should be destroyed
final ArrayList<WindowState> mDestroySurface = new ArrayList<>();

// Emergency: force-remove windows when out of memory
final ArrayList<WindowState> mForceRemoves = new ArrayList<>();

// Callbacks for "all windows drawn" events
final ArrayMap<WindowContainer<?>, Message> mWaitingForDrawnCallbacks = new ArrayMap<>();

// Windows that hide non-system overlay windows (FLAG_HIDE_NON_SYSTEM_OVERLAY_WINDOWS)
private ArrayList<WindowState> mHidingNonSystemOverlayWindows = new ArrayList<>();

// Key interception info for each input token
final Map<IBinder, KeyInterceptionInfo> mKeyInterceptionInfoForToken =
        Collections.synchronizedMap(new ArrayMap<>());

// IME display policy cache (accessed without lock)
volatile Map<Integer, Integer> mDisplayImePolicyCache =
        Collections.unmodifiableMap(new ArrayMap<>());
```

The `mGlobalLock` (`WindowManagerGlobalLock`) is the central synchronization primitive shared between WMS and `ActivityTaskManagerService`. All window hierarchy modifications must hold this lock.

### 23.1.10 Window Session

Each application process that creates windows establishes a `Session` with WMS via `IWindowSession`. The session is a per-process Binder connection that provides the API for:

- Adding windows (`addToDisplayAsUser`)
- Removing windows (`remove`)
- Relayout (size/position changes) (`relayout`)
- Finishing drawing (`finishDrawing`)
- Window positioning updates
- Input event delivery setup

```mermaid
sequenceDiagram
    participant App as Application Process
    participant VRI as ViewRootImpl
    participant WMS as WindowManagerService
    participant Sess as Session

    App->>VRI: WindowManager.addView()
    VRI->>WMS: openSession()
    WMS->>Sess: new Session(callerPid, callerUid)
    WMS-->>VRI: IWindowSession

    VRI->>Sess: addToDisplayAsUser(window, attrs, displayId)
    Sess->>WMS: addWindow(session, window, attrs)
    Note over WMS: Create WindowState<br/>Add to hierarchy<br/>Create SurfaceControl

    VRI->>Sess: relayout(window, attrs, requestedWidth, requestedHeight)
    Sess->>WMS: relayoutWindow(session, window, attrs, ...)
    Note over WMS: Compute new frames<br/>Create/resize Surface

    VRI->>Sess: finishDrawing(window,
    Sess->>WMS: finishDrawingWindow(session, window)
    Note over WMS: Mark window as drawn<br/>May trigger transition readiness
```

### 23.1.11 The Global Lock and Thread Safety

The `WindowManagerGlobalLock` (`mGlobalLock`) is one of the most contended locks in the system server. It protects:

- All `WindowContainer` hierarchy operations
- Window state changes (visibility, focus, configuration)
- Surface transaction preparation
- Display configuration changes

The lock is shared between WMS and ATMS to avoid deadlocks when operations span both services. In the animation system, a separate `SurfaceAnimationThread` is used for posting animation callbacks to avoid holding `mGlobalLock` during frame callbacks.

WMS also uses several specialized mechanisms to reduce lock contention:

1. **Volatile caches**: `mDisplayImePolicyCache` is a volatile `Map` that can be read without the lock
2. **Handler posting**: Operations that need the lock but are not urgent are posted to the `WindowManagerService.H` handler
3. **Read-only snapshots**: `InsetsState`, `TransitionInfo`, and `TaskInfo` are snapshot objects that can be sent to other threads/processes without holding the lock

### 23.1.12 BLASTSyncEngine

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/BLASTSyncEngine.java`

`BLASTSyncEngine` is the synchronization mechanism that ensures all windows participating in a transition have redrawn their content before the transition animates. Its name comes from "Buffer Layered Ahead of SurfaceFlinger Transaction" (BLAST), the buffer delivery mechanism that replaced the legacy `BufferQueue` consumer-side model.

The sync engine operates in five steps, as documented in the source:

1. **Open sync set**: `startSyncSet(TransactionReadyListener)` -- returns an ID
2. **Add participants**: `addToSyncSet(id, WindowContainer)` -- registers containers
3. **Apply changes**: Configuration changes, reparents, visibility changes
4. **Mark ready**: `setReady(id)` -- signals that all changes have been made
5. **Wait for draw**: Each participant redraws; when all are done, `transactionReady` fires

Sync methods:
```java
METHOD_UNDEFINED = -1; // No method specified
METHOD_NONE = 0;       // Apps draw internally, just report completion
METHOD_BLAST = 1;      // Apps send buffers to be applied in sync
```

The parallel sync system prevents dependency cycles: if sync B depends on sync A and a container is added to A that is already watched by B, the container is moved from B to A rather than creating a cycle.

### 23.1.13 DisplayContent Internals

`DisplayContent` (over 7,700 lines in the Android 17 tree) maintains extensive state for its display. Key internal structures beyond those already discussed:

```java
// Display metrics and configuration
int mInitialDisplayWidth, mInitialDisplayHeight;
int mInitialDisplayDensity;
float mInitialPhysicalXDpi, mInitialPhysicalYDpi;
DisplayCutout mInitialDisplayCutout;
RoundedCorners mInitialRoundedCorners;
DisplayShape mInitialDisplayShape;

// Overridable metrics (via adb shell wm size/density)
int mBaseDisplayWidth, mBaseDisplayHeight;
int mBaseDisplayDensity;
boolean mIsSizeForced, mIsDensityForced;

// Display policy and rotation
final DisplayPolicy mDisplayPolicy;
final DisplayRotation mDisplayRotation;
DisplayFrames mDisplayFrames;

// Token registry (IBinder → WindowToken)
private final HashMap<IBinder, WindowToken> mTokenMap = new HashMap();

// Gesture exclusion zones
private final Region mSystemGestureExclusion = new Region();
private int mSystemGestureExclusionLimit;

// Keep-clear areas (for PiP avoidance, etc.)
Set<Rect> mRestrictedKeepClearAreas = new ArraySet<>();
Set<Rect> mUnrestrictedKeepClearAreas = new ArraySet<>();

// Layout state
private boolean mLayoutNeeded;
int pendingLayoutChanges;
boolean mWaitingForConfig;

// PiP task controller
final PinnedTaskController mPinnedTaskController;

// Display area policy (controls DisplayArea hierarchy)
final DisplayAreaPolicy mDisplayAreaPolicy;

// Content recording (screen capture/mirror)
@Nullable ContentRecorder mContentRecorder;
```

The `mDisplayAreaPolicy` is critical: it is created by the `DisplayAreaPolicy.Provider` (configured in WMS) and determines how the `DisplayArea` hierarchy is structured for this display. Different device types can provide different policies.

The display tracks rotation through `mDisplayRotation` and maintains rotation-dependent caches for:

- Display cutout geometry (`mDisplayCutoutCache`)
- Rounded corner geometry (`mRoundedCornerCache`)
- Privacy indicator bounds (`mPrivacyIndicatorBoundsCache`)
- Display shape (`mDisplayShapeCache`)

These caches use `RotationCache` to avoid recomputing geometry on every rotation change, only recalculating when the rotation actually differs.

---

## 23.2 WM Shell Library

### 23.2.1 Shell vs Core: The Architectural Split

The window system is split into two halves:

| Aspect | WM Core | WM Shell |
|--------|---------|----------|
| **Location** | `frameworks/base/services/core/.../server/wm/` | `frameworks/base/libs/WindowManager/Shell/` |
| **Process** | System server (main WM thread) | System server (SystemUI / Shell thread) |
| **Role** | Policy engine -- decides *what* happens | Presentation engine -- decides *how* it looks |
| **API Surface** | Internal to system server | Exports via AIDL to SystemUI and Launcher |
| **Window access** | Direct WindowState/Task manipulation | TaskOrganizer callbacks, SurfaceControl |
| **Animation** | Triggers transitions, manages sync | Receives TransitionInfo, animates surfaces |

The split was introduced to allow OEMs and system components (SystemUI, Launcher) to customize window behavior without modifying core WM policy. WM Core signals intent ("this task is entering PiP"), and Shell decides presentation ("animate with this curve to this corner").

### 23.2.2 Shell Directory Structure

The Shell library is organized into feature modules:

```
frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/
├── ShellTaskOrganizer.java          — Central task lifecycle listener
├── RootTaskDisplayAreaOrganizer.java — Display area management
├── RootDisplayAreaOrganizer.java     — Root display area control
├── WindowManagerShellWrapper.java    — WMS API wrapper
├── dagger/                           — Dependency injection modules
│   ├── WMShellModule.java           — Phone-specific providers
│   ├── WMShellBaseModule.java       — Shared providers
│   ├── WMShellConcurrencyModule.java — Threading configuration
│   ├── TvWMShellModule.java         — TV-specific providers
│   ├── WMComponent.java            — Dagger component definition
│   └── WMSingleton.java            — Scope annotation
├── transition/                       — Transition animation system
│   ├── Transitions.java             — Master transition player
│   ├── DefaultTransitionHandler.java — Default animations
│   ├── MixedTransitionHandler.java  — Cross-feature transitions
│   └── RemoteTransitionHandler.java — Launcher remote transitions
├── splitscreen/                      — Split-screen feature
│   ├── StageCoordinator.java        — Split layout management
│   ├── SplitScreenController.java   — API surface
│   └── SplitScreenTransitions.java  — Split-specific animations
├── pip/                              — Picture-in-Picture
│   ├── PipTaskOrganizer.java        — PiP task management
│   ├── PipTransition.java           — PiP transition handler
│   └── PipAnimationController.java  — PiP animation logic
├── bubbles/                          — Bubble notifications
│   ├── BubbleController.java        — Bubble lifecycle
│   ├── BubbleStackView.java         — Bubble UI
│   └── BubbleTransitions.java       — Bubble animations
├── desktopmode/                      — Desktop windowing
│   ├── DesktopTasksController.kt    — Desktop task management
│   ├── DesktopTasksLimiter.kt       — Task count limits
│   └── WindowDragTransitionHandler.kt — Drag-to-move
├── freeform/                         — Freeform windowing
│   ├── FreeformTaskListener.java    — Freeform task events
│   └── FreeformTaskTransitionHandler.java — Freeform animations
├── back/                             — Predictive back gestures
│   ├── BackAnimationController.java — Back gesture handling
│   └── CrossTaskBackAnimation.java  — Cross-task animations
├── windowdecor/                      — Window decorations (caption bars)
├── onehanded/                        — One-handed mode
├── unfold/                           — Foldable unfold animation
├── recents/                          — Recent apps integration
├── fullscreen/                       — Fullscreen task listener
├── keyguard/                         — Keyguard transition handler
├── common/                           — Shared utilities
├── sysui/                            — SystemUI integration
├── animation/                        — Animation utilities
└── protolog/                         — ProtoLog configuration
```

### 23.2.3 ShellTaskOrganizer

`ShellTaskOrganizer` is the central hub through which Shell receives task lifecycle events from WM Core. It extends `TaskOrganizer` and dispatches events to registered listeners based on windowing mode.

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/ShellTaskOrganizer.java`

The listener type system routes tasks to the appropriate feature module:

```java
// Listener types registered with ShellTaskOrganizer
TASK_LISTENER_TYPE_FULLSCREEN  → FullscreenTaskListener
TASK_LISTENER_TYPE_MULTI_WINDOW → StageCoordinator (split-screen)
TASK_LISTENER_TYPE_PIP         → PipTaskOrganizer
TASK_LISTENER_TYPE_FREEFORM    → FreeformTaskListener
TASK_LISTENER_TYPE_DESKTOP_MODE → DesktopTasksController
```

When WM Core changes a task's windowing mode, `ShellTaskOrganizer` automatically reroutes the task to the appropriate listener. This is the mechanism by which, for example, entering PiP transfers task management from the fullscreen listener to `PipTaskOrganizer`.

### 23.2.4 Dependency Injection Architecture

Shell uses Dagger 2 for dependency injection, organized into a layered module hierarchy:

```mermaid
graph TB
    subgraph "DI Module Hierarchy"
        BASE["WMShellBaseModule<br/>(shared across all device types)"]
        CONC["WMShellConcurrencyModule<br/>(threading configuration)"]
        PHONE["WMShellModule<br/>(phone-specific providers)"]
        TV["TvWMShellModule<br/>(TV-specific providers)"]
        COMP["WMComponent<br/>(Dagger component)"]
    end

    BASE --> COMP
    CONC --> COMP
    PHONE --> COMP
    TV -.-> COMP

    subgraph "Key Bindings"
        B1["ShellTaskOrganizer"]
        B2["Transitions"]
        B3["SplitScreenController"]
        B4["PipController"]
        B5["BubbleController"]
        B6["DesktopTasksController"]
        B7["BackAnimationController"]
    end

    COMP --> B1
    COMP --> B2
    COMP --> B3
    PHONE --> B4
    PHONE --> B5
    PHONE --> B6
    PHONE --> B7

    style BASE fill:#e8f5e9
    style PHONE fill:#e1f5fe
    style TV fill:#fff3e0
```

**Source files:**

- `WMShellBaseModule.java` -- Provides components shared across all variants (ShellTaskOrganizer, Transitions, DisplayController, SyncTransactionQueue)
- `WMShellModule.java` -- Phone/tablet-specific components (PIP phone implementation, Bubbles, Desktop mode, Split-screen)
- `TvWMShellModule.java` -- TV-specific components (PIP TV implementation, no Bubbles)
- `WMShellConcurrencyModule.java` -- Threading infrastructure

The `@WMSingleton` scope annotation ensures that components like `ShellTaskOrganizer` and `Transitions` are singletons within the Shell component:

```java
@WMSingleton
@Component(modules = {
    WMShellBaseModule.class,
    WMShellConcurrencyModule.class,
    WMShellModule.class,          // or TvWMShellModule for TV
    ShellBackAnimationModule.class,
    PipModule.class,
    PinnedLayerModule.class,
})
public interface WMComponent { ... }
```

Per-variant customization is achieved by swapping the device-specific module. For example, TV replaces `WMShellModule` with `TvWMShellModule`, which provides a TV-specific PIP implementation and omits Bubbles entirely.

### 23.2.5 Shell Communication Model

Shell communicates with external components via multiple channels:

```mermaid
graph TB
    subgraph "System Server Process"
        subgraph "WM Core"
            WMS_["WindowManagerService"]
            TC_["TransitionController"]
            WOC_["WindowOrganizerController"]
        end

        subgraph "WM Shell"
            STO_["ShellTaskOrganizer"]
            TR_["Transitions"]
            SI_["ShellInterface"]
        end
    end

    subgraph "SystemUI Process"
        WMSh_["WMShell<br/>(Dagger in-process)"]
    end

    subgraph "Launcher Process"
        QS_["Quickstep<br/>(AIDL binder)"]
    end

    WOC_ -->|"TaskOrganizer callbacks<br/>(in-process)"| STO_
    TC_ -->|"ITransitionPlayer<br/>(in-process)"| TR_

    SI_ -->|"Dagger injection<br/>(in-process same classloader)"| WMSh_
    SI_ -->|"AIDL Binder IPC<br/>(cross-process)"| QS_

    style WMS_ fill:#e1f5fe
    style TR_ fill:#f3e5f5
```

**In-process communication (Shell to WM Core)**:

- Shell calls WM Core APIs (e.g., `TaskOrganizer.applyTransaction()`) directly since they share the system server process
- WM Core calls Shell via organizer callbacks (`TaskOrganizer.onTaskAppeared()`, `ITransitionPlayer.onTransitionReady()`)
- These calls cross thread boundaries (WM thread to Shell thread) via Handler posting

**In-process communication (Shell to SystemUI)**:

- SystemUI loads Shell as a Dagger component within its process
- Shell provides interfaces (e.g., `Pip`, `SplitScreen`, `Bubbles`) via Dagger injection
- Communication is direct Java method calls with thread annotations (`@ExternalThread`, `@ShellMainThread`)

**Cross-process communication (Shell to Launcher)**:

- Launcher communicates via AIDL binder interfaces (`IShellTransitions`, `ISplitScreen`, `IBackAnimation`, etc.)
- Shell provides binder implementations via `ExternalInterfaceBinder` pattern
- Calls are dispatched from the binder thread to the Shell main thread

### 23.2.6 Threading Model

Shell uses a multi-threaded architecture with explicit thread annotations and executor-based dispatch:

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/dagger/WMShellConcurrencyModule.java`

```mermaid
graph LR
    subgraph "Thread Pool"
        SYSUI["SysUI Main Thread<br/>(@ExternalMainThread)<br/>Looper.getMainLooper()"]
        SHELL["Shell Main Thread<br/>(@ShellMainThread)<br/>'wmshell.main'<br/>THREAD_PRIORITY_DISPLAY"]
        ANIM["Shell Animation Thread<br/>(@ShellAnimationThread)<br/>'wmshell.anim'<br/>THREAD_PRIORITY_DISPLAY"]
        BG["Shell Background Thread<br/>(@ShellBackgroundThread)<br/>'wmshell.background'<br/>THREAD_PRIORITY_BACKGROUND"]
        SPLASH["Shell Splash Thread<br/>(@ShellSplashscreenThread)<br/>'wmshell.splashscreen'"]
        DESKTOP["Shell Desktop Thread<br/>(@ShellDesktopThread)<br/>'wmshell.desktop'<br/>THREAD_PRIORITY_FOREGROUND"]
    end

    SYSUI -->|"ExternalThread<br/>annotations"| SHELL
    SHELL -->|"Animation<br/>dispatch"| ANIM
    SHELL -->|"I/O, persistence"| BG
```

The `@ShellMainThread` is the primary execution thread for Shell components. It runs at `THREAD_PRIORITY_DISPLAY` priority, the same as the SurfaceFlinger and RenderThread, ensuring that window management operations are not preempted by lower-priority work.

The threading model enforces a strict contract:

- Shell components execute on `@ShellMainThread`
- SystemUI calls into Shell via `@ExternalMainThread` executors that post to the Shell thread
- Launcher calls into Shell via AIDL binder, which also dispatches to the Shell thread
- Animations that need frame-perfect timing use `@ShellAnimationThread`
- Heavy operations (snapshot capture, persistence) use `@ShellBackgroundThread`

The `enableShellMainThread()` configuration check determines whether a dedicated Shell thread is created, or whether Shell reuses the SysUI main thread:

```java
public static boolean enableShellMainThread(Context context) {
    return context.getResources().getBoolean(R.bool.config_enableShellMainThread);
}
```

Message queue monitoring thresholds are set at 30ms for both delivery and dispatch, enabling detection of thread contention in debug builds:

```java
private static final int MSGQ_SLOW_DELIVERY_THRESHOLD_MS = 30;
private static final int MSGQ_SLOW_DISPATCH_THRESHOLD_MS = 30;
```

---

## 23.3 Transition System

### 23.3.1 Overview: From Legacy AppTransition to Shell Transitions

The transition system manages how window changes (opening, closing, resizing, rotating) are animated. Android has evolved from a legacy `AppTransition` system (where WM Core both decided and animated transitions) to a "Shell Transitions" architecture where WM Core collects participating windows and Shell drives the animation.

The Shell Transitions system (`ENABLE_SHELL_TRANSITIONS = true`) is now the primary path. The key benefit is that Shell can orchestrate complex multi-window animations (e.g., entering split-screen with two tasks simultaneously) that the legacy system could not handle.

### 23.3.2 TransitionController (WM Core Side)

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/TransitionController.java` (over 2,200 lines)

`TransitionController` manages the collection and synchronization phases of transitions on the WM Core side. Its Javadoc provides the key architectural insight:

> *"Currently, only 1 transition can be the primary 'collector' at a time. However, collecting can actually be broken into two phases: (1) Actually making WM changes and recording the participating containers. (2) Waiting for the participating containers to become ready (eg. redrawing content). Because (2) takes most of the time AND doesn't change WM, we can actually have multiple transitions in phase (2) concurrently with one in phase (1). We refer to this arrangement as 'parallel' collection."*

Key design points:

- **Parallel collection**: Multiple transitions can wait for readiness simultaneously, but only one can actively collect participants
- **Track assignment**: When a transition moves to "playing", it is checked against all other playing transitions. If it does not overlap, it gets a new "track" for parallel animation. If it overlaps with transitions in more than one track, it is marked SYNC and waits for all prior animations to finish.
- **Timeout management**: `DEFAULT_TIMEOUT_MS` (5000ms) for transitions involving app startup; `CHANGE_TIMEOUT_MS` (2000ms) for configuration changes

```java
class TransitionController {
    private static final int DEFAULT_TIMEOUT_MS = 5000;
    private static final int CHANGE_TIMEOUT_MS = 2000;

    static final int SYNC_METHOD =
            SystemProperties.getBoolean("persist.wm.debug.shell_transit_blast", false)
                    ? BLASTSyncEngine.METHOD_BLAST : BLASTSyncEngine.METHOD_NONE;
}
```

### 23.3.3 Transition (WM Core Side)

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/Transition.java` (nearly 5,000 lines)

Each `Transition` instance represents a single transition from creation through collection, readiness, playing, and completion. The transition types are defined in `WindowManager`:

| Constant | Value | Description |
|----------|-------|-------------|
| `TRANSIT_OPEN` | 1 | Window/task appearing |
| `TRANSIT_CLOSE` | 2 | Window/task disappearing |
| `TRANSIT_TO_FRONT` | 3 | Existing task moving to front |
| `TRANSIT_TO_BACK` | 4 | Task moving to back |
| `TRANSIT_CHANGE` | 6 | Configuration change (rotation, bounds) |
| `TRANSIT_PIP` | 8 | Entering Picture-in-Picture |
| `TRANSIT_SLEEP` | 9 | Display going to sleep |
| `TRANSIT_WAKE` | 10 | Display waking up |

The `Transition` class tracks:

- **Participants**: Which `WindowContainer` nodes are participating
- **Changes**: What changed for each participant (open, close, change, etc.)
- **Animation options**: Per-activity animation overrides, cross-profile animations
- **Sync state**: Whether all participants have redrawn their content

### 23.3.4 Transitions (Shell Side -- The Animation Player)

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/transition/Transitions.java`

The Shell-side `Transitions` class is the master animation orchestrator. It implements `ITransitionPlayer` and manages the lifecycle of transitions from the Shell perspective:

```
--start--> PENDING --onTransitionReady--> READY --play--> ACTIVE --finish--> |
                                                --merge--> MERGED --^
```

```mermaid
stateDiagram-v2
    [*] --> PENDING: startTransition / requestTransition
    PENDING --> READY: onTransitionReady with TransitionInfo
    READY --> ACTIVE: play with handler
    READY --> MERGED: merge into active
    ACTIVE --> [*]: finish
    MERGED --> [*]: parent finishes
```

Shell defines custom transition types beyond the core types for feature-specific transitions:

```java
// Shell-specific custom transition types (TRANSIT_FIRST_CUSTOM + N)
TRANSIT_EXIT_PIP              = TRANSIT_FIRST_CUSTOM + 1;
TRANSIT_EXIT_PIP_TO_SPLIT     = TRANSIT_FIRST_CUSTOM + 2;
TRANSIT_REMOVE_PIP            = TRANSIT_FIRST_CUSTOM + 3;
TRANSIT_SPLIT_SCREEN_PAIR_OPEN = TRANSIT_FIRST_CUSTOM + 4;
TRANSIT_SPLIT_SCREEN_OPEN_TO_SIDE = TRANSIT_FIRST_CUSTOM + 5;
TRANSIT_SPLIT_DISMISS_SNAP    = TRANSIT_FIRST_CUSTOM + 6;
TRANSIT_SPLIT_DISMISS         = TRANSIT_FIRST_CUSTOM + 7;
TRANSIT_MAXIMIZE              = TRANSIT_FIRST_CUSTOM + 8;
TRANSIT_RESTORE_FROM_MAXIMIZE = TRANSIT_FIRST_CUSTOM + 9;
TRANSIT_PIP_BOUNDS_CHANGE     = TRANSIT_FIRST_CUSTOM + 16;
TRANSIT_MINIMIZE              = TRANSIT_FIRST_CUSTOM + 20;
```

### 23.3.5 Transition Handler Chain

Shell uses a handler chain to dispatch transitions to the appropriate feature module:

```mermaid
graph TB
    subgraph "Transition Handler Chain"
        TI["TransitionInfo from WM Core"]
        TI --> MH["MixedTransitionHandler<br/>(cross-feature transitions)"]
        MH -->|"not handled"| KH["KeyguardTransitionHandler<br/>(keyguard occlude/unocclude)"]
        KH -->|"not handled"| SH["SleepHandler<br/>(sleep/wake transitions)"]
        SH -->|"not handled"| PT["PipTransition<br/>(PiP enter/exit)"]
        PT -->|"not handled"| SCT["SplitScreenTransitions<br/>(split enter/exit)"]
        SCT -->|"not handled"| FTH["FreeformTaskTransitionHandler<br/>(freeform bounds changes)"]
        FTH -->|"not handled"| RTH["RemoteTransitionHandler<br/>(Launcher remote transitions)"]
        RTH -->|"not handled"| DTH["DefaultTransitionHandler<br/>(standard open/close/change)"]
    end

    style TI fill:#e1f5fe
    style DTH fill:#e8f5e9
```

Each handler in the chain implements `TransitionHandler` and can either:

1. **Claim** the transition by returning `true` from `startAnimation()`, taking responsibility for calling `finishTransition()` when done
2. **Decline** by returning `false`, passing it to the next handler
3. **Request merging** with a currently playing transition if the transitions are compatible

The `MixedTransitionHandler` is special: it handles transitions that involve multiple features simultaneously (e.g., entering split-screen while another window is entering PiP).

### 23.3.6 Transition Lifecycle: End-to-End Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant WMS as WM Core
    participant TC as TransitionController
    participant T as Transition
    participant BSE as BLASTSyncEngine
    participant TR as Shell Transitions
    participant Handler as TransitionHandler
    participant SF as SurfaceFlinger

    App->>WMS: startActivity()
    WMS->>TC: requestStartTransition(TRANSIT_OPEN)
    TC->>T: new Transition()
    TC->>TR: onTransitionStartRequested()
    Note over T: COLLECTING phase

    WMS->>T: collect(openingTask)
    WMS->>T: collect(closingTask)
    T->>BSE: startSyncSet()
    Note over T: Wait for participants to redraw

    App-->>BSE: finishDrawing()
    BSE-->>TC: onSyncFinished()
    Note over T: READY phase

    TC->>TR: onTransitionReady(TransitionInfo)
    TR->>Handler: startAnimation(TransitionInfo, startTransaction, finishTransaction)
    Note over Handler: ACTIVE phase

    Handler->>SF: startTransaction.apply()
    Note over Handler: Animate surfaces...
    Handler->>SF: finishTransaction.apply()
    Handler->>TR: finishTransition()
    TR->>TC: onTransitionFinished()
    Note over T: FINISHED
```

The two SurfaceControl.Transactions -- `startTransaction` and `finishTransaction` -- are critical:

- **startTransaction**: Applied at animation start; sets up the initial animation state (may show/hide surfaces, set initial positions)
- **finishTransaction**: Applied at animation end; sets the final state (final positions, final visibility). This is the "ground truth" that persists after the animation.

### 23.3.7 TransitionInfo: The Data Contract

`TransitionInfo` is the data object passed from WM Core to Shell that describes everything Shell needs to animate a transition:

```mermaid
classDiagram
    class TransitionInfo {
        +int type
        +int flags
        +List~Change~ changes
        +SurfaceControl.Transaction startTransaction
        +SurfaceControl.Transaction finishTransaction
    }

    class Change {
        +WindowContainerToken container
        +SurfaceControl leash
        +int mode
        +int flags
        +Rect startAbsBounds
        +Rect endAbsBounds
        +Rect endRelOffset
        +int startRotation
        +int endRotation
        +ActivityManager.RunningTaskInfo taskInfo
        +AnimationOptions animationOptions
    }

    TransitionInfo --> Change : contains 1..*
```

Each `Change` in the `TransitionInfo` represents one participating container with:

- Its `mode` (OPEN, CLOSE, TO_FRONT, TO_BACK, CHANGE)
- Its `flags` (IS_WALLPAPER, IS_INPUT_METHOD, IS_DISPLAY, FILLS_TASK, TRANSLUCENT, etc.)
- Start and end bounds for interpolation
- Start and end rotation for rotation animations
- A `leash` SurfaceControl that Shell can animate

Flags on individual changes provide Shell with enough context to decide animations:

```java
FLAG_IS_WALLPAPER            // This change is a wallpaper
FLAG_IS_INPUT_METHOD         // This change is the IME
FLAG_IS_DISPLAY              // This change represents a display-level transition
FLAG_FILLS_TASK              // Activity fills its task bounds
FLAG_TRANSLUCENT             // Activity has translucent windows
FLAG_SHOW_WALLPAPER          // Activity shows wallpaper behind
FLAG_NO_ANIMATION            // Suppress animation for this change
FLAG_IS_BEHIND_STARTING_WINDOW // Hidden behind splash screen
FLAG_MOVED_TO_TOP            // Container moved to top of z-order
FLAG_IN_TASK_WITH_EMBEDDED_ACTIVITY // Container in embedded activity task
FLAG_DISPLAY_HAS_ALERT_WINDOWS // Display has visible alert windows
FLAG_TASK_LAUNCHING_BEHIND   // Task launching behind current
FLAG_IS_VOICE_INTERACTION    // Voice interaction window
FLAG_IS_OCCLUDED             // Occluded by keyguard
FLAG_CONFIG_AT_END           // Configuration applies at animation end
FLAG_WILL_IME_SHOWN          // IME will be shown after transition
```

### 23.3.8 Transition Merging

When multiple transitions are ready concurrently within the same track, the system attempts to **merge** them. Merging combines a new transition into an already-playing transition, allowing the animation to smoothly incorporate additional changes without restarting.

The merge flow:

```mermaid
sequenceDiagram
    participant TC as TransitionController
    participant TR as Shell Transitions
    participant H1 as Active Handler
    participant T_Active as Active Transition
    participant T_New as New Transition

    TR->>H1: Can you merge T_New into T_Active?
    alt Merge accepted
        H1->>TR: mergeAnimation(T_New, into T_Active)
        Note over H1: Adjust animation to<br/>incorporate new changes
        T_New-->>TR: Moved to MERGED state
    else Merge rejected
        TR->>TR: Queue T_New in READY state
        Note over TR: T_New waits for<br/>T_Active to finish
    end
```

Common merge scenarios:

- Opening multiple activities in rapid succession (second merge into first)
- Configuration change while an app transition is animating
- IME show/hide during an app transition

### 23.3.9 Parallel Tracks

The track system enables true parallel animation. When WM Core determines that a new transition does not overlap with any currently playing transitions, it assigns the transition to a new track:

```
Track 0: [Transition A: Task 1 open] → [Transition C: Task 1 close]
Track 1: [Transition B: Task 2 change] → [Transition D: Task 2 PiP]
```

Transitions within a track are serialized. Transitions across tracks play simultaneously.

If a transition overlaps with more than one track (e.g., it involves containers from both Track 0 and Track 1), it is marked as SYNC. A SYNC transition blocks until all active tracks finish their current animations, then plays exclusively.

### 23.3.10 DefaultTransitionHandler

`DefaultTransitionHandler` is the fallback handler that provides standard Android window animations. It handles:

- **Open/close**: Fade in/out with optional scale
- **To front/back**: Existing window moving in z-order
- **Change**: Bounds change, rotation change
- **Wallpaper transitions**: Parallax and cross-fade with wallpaper

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/transition/DefaultTransitionHandler.java`

The `DefaultTransitionHandler` creates `SurfaceControl.Transaction` frame callbacks via `ValueAnimator` to smoothly interpolate surface properties (position, size, alpha, corner radius) from start to end state.

### 23.3.11 RemoteTransitionHandler

`RemoteTransitionHandler` enables external components (primarily Launcher/Quickstep) to register `RemoteTransition` objects that handle specific transitions. This is how Launcher provides its custom recents animation, app-to-home animation, and app launch animation.

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/transition/RemoteTransitionHandler.java`

Remote transitions use `TransitionFilter` to match specific transition patterns (e.g., "closing an app to show home"). When a match is found, the remote handler forwards the `TransitionInfo` to the remote component via AIDL.

---

## 23.4 Multi-Window Architecture

### 23.4.1 Windowing Modes

Android defines five windowing modes in `WindowConfiguration`:

**Source file:** `frameworks/base/core/java/android/app/WindowConfiguration.java`

```java
public static final int WINDOWING_MODE_UNDEFINED   = 0;
public static final int WINDOWING_MODE_FULLSCREEN  = 1;
public static final int WINDOWING_MODE_PINNED      = 2;  // Picture-in-Picture
public static final int WINDOWING_MODE_FREEFORM    = 5;  // Freely resizable
public static final int WINDOWING_MODE_MULTI_WINDOW = 6; // Split-screen
```

The windowing mode determines a task's layout behavior:

| Mode | Bounds | User Resizable | Z-Order | Use Case |
|------|--------|----------------|---------|----------|
| FULLSCREEN | Fills display | No | Normal stacking | Default phone mode |
| PINNED | Small fixed rect | Limited | Always on top | Video PiP |
| FREEFORM | User-defined rect | Yes (drag edges) | Normal stacking | Desktop mode |
| MULTI_WINDOW | Half/portion of display | Via divider | Side by side | Split screen |

The `tasksAreFloating()` helper method identifies which modes produce floating
windows. It delegates to `isFloating()`, which counts only freeform and PiP as
floating; split-screen (multi-window) is tiled, not floating:

```java
// WindowConfiguration.java
public boolean tasksAreFloating() {
    return isFloating(mWindowingMode);
}

public static boolean isFloating(@WindowingMode int windowingMode) {
    return windowingMode == WINDOWING_MODE_FREEFORM
            || windowingMode == WINDOWING_MODE_PINNED;
}
```

### 23.4.2 Split Screen Architecture

Split screen divides the display into two stages, each hosting one or more tasks. The architecture spans both WM Core and Shell.

**Key source files:**

- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/splitscreen/StageCoordinator.java`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/splitscreen/SplitScreenController.java`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/splitscreen/StageTaskListener.java`

```mermaid
graph TB
    subgraph "Split Screen Architecture"
        SSC["SplitScreenController<br/>(API surface)"]
        SC["StageCoordinator<br/>(layout orchestration)"]
        SL["SplitLayout<br/>(divider + bounds)"]
        STL_A["StageTaskListener A<br/>(top/left stage)"]
        STL_B["StageTaskListener B<br/>(bottom/right stage)"]
        SST["SplitScreenTransitions<br/>(enter/exit animations)"]
    end

    SSC --> SC
    SC --> SL
    SC --> STL_A
    SC --> STL_B
    SC --> SST

    subgraph "WM Core Tasks"
        RT_A["Root Task A"]
        RT_B["Root Task B"]
        T_A["App Task A"]
        T_B["App Task B"]
    end

    STL_A -.-> RT_A
    STL_B -.-> RT_B
    RT_A --> T_A
    RT_B --> T_B

    style SC fill:#e1f5fe
    style SST fill:#f3e5f5
```

The `StageCoordinator` manages the spatial relationship between stages. Split positions are defined as constants:

```java
SPLIT_POSITION_TOP_OR_LEFT     // First stage
SPLIT_POSITION_BOTTOM_OR_RIGHT // Second stage
SPLIT_POSITION_UNDEFINED       // Not in split
```

Snap positions define the divider ratios:

```java
SNAP_TO_2_50_50  // Equal split
SNAP_TO_2_10_90  // First stage small
SNAP_TO_2_90_10  // First stage large
```

Split screen can also operate in "flexible" mode (`enableFlexibleSplit` flag) where more than two tasks can participate, and the divider positions are more fluid.

Exit reasons are enumerated to track why split screen was dismissed:

```java
EXIT_REASON_APP_DOES_NOT_SUPPORT_MULTIWINDOW
EXIT_REASON_APP_FINISHED
EXIT_REASON_CHILD_TASK_ENTER_PIP
EXIT_REASON_CHILD_TASK_ENTER_BUBBLE
EXIT_REASON_DESKTOP_MODE
EXIT_REASON_DEVICE_FOLDED
EXIT_REASON_DRAG_DIVIDER
EXIT_REASON_FULLSCREEN_REQUEST
EXIT_REASON_FULLSCREEN_SHORTCUT
EXIT_REASON_RETURN_HOME
EXIT_REASON_ROOT_TASK_VANISHED
EXIT_REASON_SCREEN_LOCKED_SHOW_ON_TOP
EXIT_REASON_UNKNOWN
```

### 23.4.3 Picture-in-Picture (PiP)

PiP allows a task to shrink to a small floating overlay window while the user interacts with other apps.

**Key source files:**

- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/pip/PipTaskOrganizer.java`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/pip/PipTransition.java`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/pip/PipAnimationController.java`

`PipTaskOrganizer` extends the task organizer pattern to manage the PiP task's surface directly:

```java
// Registered as TASK_LISTENER_TYPE_PIP with ShellTaskOrganizer
```

PiP animation directions define the transition phases:

```java
TRANSITION_DIRECTION_TO_PIP                  // Entering PiP
TRANSITION_DIRECTION_LEAVE_PIP               // Expanding back to fullscreen
TRANSITION_DIRECTION_LEAVE_PIP_TO_SPLIT_SCREEN // Expanding into split
TRANSITION_DIRECTION_EXPAND_OR_UNEXPAND      // User expand/collapse gesture
TRANSITION_DIRECTION_REMOVE_STACK            // Dismissing PiP entirely
TRANSITION_DIRECTION_SNAP_AFTER_RESIZE       // Snapping to edge after resize
TRANSITION_DIRECTION_USER_RESIZE             // User pinch-to-resize
TRANSITION_DIRECTION_SAME                    // No direction change
TRANSITION_DIRECTION_NONE                    // No transition
```

The PiP animation can be of two types:

- `ANIM_TYPE_BOUNDS` -- Bounds change animation (move, resize)
- `ANIM_TYPE_ALPHA` -- Alpha fade animation (enter, exit)

### 23.4.4 Freeform Mode

Freeform mode (`WINDOWING_MODE_FREEFORM`) enables desktop-style freely resizable windows. This mode is the foundation for Android's desktop windowing experience.

**Key source files:**

- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/freeform/FreeformTaskListener.java`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/freeform/FreeformTaskTransitionHandler.java`

`FreeformTaskListener` handles task appearance/vanish events and manages window decorations (caption bars) for freeform windows. `FreeformTaskTransitionHandler` animates transitions involving freeform tasks, such as entering freeform from fullscreen or resizing.

### 23.4.5 Desktop Mode

Desktop mode is an evolution of freeform that adds a full desktop windowing experience with task management, window limits, and multi-desk support.

**Key source files:**

- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/DesktopTasksController.kt`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/DesktopTasksLimiter.kt`
- `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/WindowDragTransitionHandler.kt`

The desktop mode directory contains a substantial number of components (50+ files), reflecting the complexity of a full desktop windowing experience:

```
desktopmode/
├── DesktopTasksController.kt              — Central controller
├── DesktopTasksLimiter.kt                — Enforces max open task count
├── WindowDragTransitionHandler.kt         — Drag-to-move transitions
├── DragToDesktopTransitionHandler.kt      — Drag from dock to desktop
├── DesktopImeHandler.kt                  — IME integration for freeform
├── DesktopImmersiveController.kt         — Immersive mode in desktop
├── DesktopDisplayEventHandler.kt         — Display connect/disconnect
├── DesktopModeMoveToDisplayTransitionHandler.kt — Move a desk task to another display
├── DisplayDisconnectTransitionHandler.kt  — Migrate desks off a removed display
├── DesktopPipTransitionController.kt     — PiP within desktop mode
├── DesktopTaskPosition.kt                — Window position management
├── DesktopWallpaperActivity.kt           — Desktop wallpaper surface
├── DesktopModeVisualIndicator.java       — Drag visual indicator
├── multidesks/                            — Multi-desk support (DesksController, DesksOrganizer)
├── homescreenpeeking/                     — Home-screen peek hot corners
├── desktoptaskshandlers/                  — Desk task transition handlers
├── minimize/                              — Task minimization
├── education/                             — User onboarding
├── animation/                             — Desktop-specific animations
├── data/                                  — Desktop state persistence
├── common/                                — Shared utilities
└── desktopfirst/                          — Desktop-first experience
```

Desktop mode introduces transition types specific to windowing operations:

```java
TRANSIT_MAXIMIZE              // Freeform → maximized
TRANSIT_RESTORE_FROM_MAXIMIZE // Maximized → freeform
TRANSIT_MINIMIZE              // Task minimization
```

### 23.4.6 Multi-Window Task Flow

The following diagram shows how a task transitions between windowing modes:

```mermaid
stateDiagram-v2
    [*] --> FULLSCREEN: Launch app

    FULLSCREEN --> PINNED: Enter PiP
    FULLSCREEN --> MULTI_WINDOW: Enter split screen
    FULLSCREEN --> FREEFORM: Enter desktop mode

    PINNED --> FULLSCREEN: Expand from PiP
    PINNED --> MULTI_WINDOW: PiP to split

    MULTI_WINDOW --> FULLSCREEN: Exit split - drag divider or dismiss
    MULTI_WINDOW --> PINNED: Split task enters PiP

    FREEFORM --> FULLSCREEN: Maximize / exit desktop
    FREEFORM --> PINNED: Freeform task enters PiP

    FULLSCREEN --> [*]: Task finished
    PINNED --> [*]: Dismiss PiP
    MULTI_WINDOW --> [*]: Task finished in split
    FREEFORM --> [*]: Task finished in desktop
```

Each transition between modes involves:

1. WM Core updating the task's `WindowConfiguration.windowingMode`
2. A transition being created and collected by `TransitionController`
3. The old Shell listener releasing the task and the new listener acquiring it (via `ShellTaskOrganizer`)
4. Shell animating the transition through the appropriate `TransitionHandler`

### 23.4.7 WindowContainerTransaction

`WindowContainerTransaction` (WCT) is the atomic operation mechanism that Shell uses to make changes to the window hierarchy. Rather than making individual calls to WM Core, Shell batches changes into a single WCT:

```java
WindowContainerTransaction wct = new WindowContainerTransaction();
wct.setBounds(taskToken, newBounds);           // Change bounds
wct.setWindowingMode(taskToken, FREEFORM);     // Change windowing mode
wct.reorder(taskToken, true /* onTop */);      // Reorder in z-stack
wct.reparent(taskToken, newParentToken, true); // Move to different parent

// Apply atomically via the organizer
shellTaskOrganizer.applyTransaction(wct);
```

WCT operations include:

- `setBounds()` -- Change task bounds
- `setWindowingMode()` -- Change windowing mode
- `reorder()` -- Move in z-order
- `reparent()` -- Move to different parent container
- `setFocusable()` -- Set focus policy
- `setHidden()` -- Hide/show container
- `startTask()` -- Start a pending intent in context of this transaction
- `sendPendingIntent()` -- Launch via pending intent

WCTs can be submitted with or without an associated transition. When submitted with a transition, the WCT changes are collected as part of the transition and animated by Shell.

### 23.4.8 Task and TaskFragment Hierarchy

Within the multi-window system, the task hierarchy is:

```
TaskDisplayArea
  └── Task (root task, often windowing-mode-specific)
        ├── Task (leaf task, holds activities)
        │     ├── TaskFragment (optional, for activity embedding)
        │     │     └── ActivityRecord
        │     │           └── WindowState
        │     └── ActivityRecord
        │           └── WindowState
        └── Task (another leaf task)
```

The `Task` class (over 7,500 lines) extends `TaskFragment`:

```java
class Task extends TaskFragment { ... }
```

And `TaskFragment` extends `WindowContainer`:

```java
class TaskFragment extends WindowContainer<WindowContainer> { ... }
```

This hierarchy enables:

- **Root tasks** for windowing mode grouping (e.g., a split-screen root task contains two leaf tasks)
- **Leaf tasks** for individual activities
- **TaskFragments** for activity embedding (side-by-side activities within a single task, used by Jetpack WindowManager)

### 23.4.9 Activity Record and the Window-Activity Relationship

`ActivityRecord` extends `WindowToken`, which extends `WindowContainer<WindowState>`:

```java
final class ActivityRecord extends WindowToken { ... }
class WindowToken extends WindowContainer<WindowState> { ... }
```

This means an `ActivityRecord` directly contains `WindowState` children. A single activity may have multiple windows:

- The main application window (`TYPE_BASE_APPLICATION`)
- A starting/splash window (`TYPE_APPLICATION_STARTING`)
- Sub-windows (panels, media surfaces)
- Dialog windows

The `ActivityRecord` manages the activity lifecycle states (INITIALIZING, STARTED, RESUMED, PAUSED, STOPPED, FINISHING, DESTROYED), and these states influence window visibility and transition behavior.

### 23.4.10 Bounds Computation

Multi-window bounds are computed through a cascade:

```mermaid
graph TB
    DC["DisplayContent bounds<br/>(full display)"]
    TDA["TaskDisplayArea bounds<br/>(display minus system bars)"]
    ROOT["Root Task bounds<br/>(may be split portion)"]
    LEAF["Leaf Task bounds<br/>(may have margins)"]
    AR["ActivityRecord bounds<br/>(letterboxed if needed)"]
    WS["WindowState frame<br/>(final layout)"]

    DC --> TDA
    TDA --> ROOT
    ROOT --> LEAF
    LEAF --> AR
    AR --> WS

    style DC fill:#e8f5e9
    style WS fill:#e1f5fe
```

Each level can constrain or transform the bounds:

- **DisplayContent**: Full display dimensions minus notch/cutout if applicable
- **TaskDisplayArea**: Display area after subtracting persistent system UI
- **Root Task**: In split mode, this is half (or a portion) of the task display area
- **Leaf Task**: May have additional constraints (minimum size, aspect ratio)
- **ActivityRecord**: May be letterboxed if the activity does not support the available bounds
- **WindowState**: Final frame computed by layout, accounting for insets and compatibility scaling

---

## 23.5 Multi-Display

### 23.5.1 DisplayContent and the Display Model

Each connected display (physical or virtual) is represented by a `DisplayContent` instance in the window hierarchy. The `RootWindowContainer` at the top of the hierarchy contains one `DisplayContent` child per display.

```mermaid
graph TB
    RWC["RootWindowContainer"]
    DC0["DisplayContent<br/>mDisplayId=0<br/>(Internal)"]
    DC1["DisplayContent<br/>mDisplayId=1<br/>(External HDMI)"]
    DC2["DisplayContent<br/>mDisplayId=2<br/>(Virtual - Cast)"]

    RWC --> DC0
    RWC --> DC1
    RWC --> DC2

    subgraph "Display 0 Hierarchy"
        DA0["DisplayArea.Root"]
        TDA0["TaskDisplayArea"]
        IME0["ImeContainer"]
    end

    subgraph "Display 1 Hierarchy"
        DA1["DisplayArea.Root"]
        TDA1["TaskDisplayArea"]
        IME1["ImeContainer"]
    end

    DC0 --> DA0
    DA0 --> TDA0
    DA0 --> IME0

    DC1 --> DA1
    DA1 --> TDA1
    DA1 --> IME1
```

Each `DisplayContent` is self-contained with its own:

- `DisplayArea` hierarchy (configured by `DisplayAreaPolicy`)
- `InsetsStateController` (system bar insets are per-display)
- `InputMonitor` (input window list is per-display)
- `DisplayFrames` (screen bounds, cutout, insets)
- Focus tracking (per-display focused window)
- IME container (IME can be local or fallback to default display)

### 23.5.2 Display Identification

Displays use two identification schemes:

| Identifier | Type | Stability | Source |
|-----------|------|-----------|--------|
| `mDisplayId` | `int` | Stable within boot | Assigned by `DisplayManagerService` |
| `mCurrentUniqueDisplayId` | `String` | Can change at runtime | Physical display EDID or virtual display token |

The `mCurrentUniqueDisplayId` can change if the underlying physical display hardware changes (e.g., hot-plugging a different monitor), while `mDisplayId` remains stable for the lifetime of the `DisplayContent`.

### 23.5.3 Virtual Displays

Virtual displays are created via `DisplayManagerService` and backed by a `Surface` rather than physical hardware. They are used for:

- **Screen casting/mirroring** -- Content is rendered to a virtual display, captured, and sent over network
- **Presentation API** -- `android.app.Presentation` renders to a virtual display for secondary screens
- **Companion devices** -- Virtual device framework creates virtual displays for remote devices
- **Testing** -- Instrumentation creates virtual displays for multi-display tests

Virtual display flags control behavior:

| Flag | Effect |
|------|--------|
| `FLAG_PRIVATE` | Content only visible to creating process |
| `FLAG_SHOULD_SHOW_SYSTEM_DECORATIONS` | Display gets status/navigation bars |
| `FLAG_CAN_SHOW_WITH_INSECURE_KEYGUARD` | Can show content when keyguard is active |
| `FLAG_ALLOWS_CONTENT_MODE_SWITCH` | Display content mode can change |

### 23.5.4 Cross-Display Window Movement

Tasks can be moved between displays via several mechanisms:

1. **WindowContainerTransaction**: Shell issues a `WindowContainerTransaction` that reparents a task to a different display's `TaskDisplayArea`
2. **Activity launch targeting**: An activity can be launched targeting a specific display via `ActivityOptions.setLaunchDisplayId()`
3. **Display disconnect**: When a display is removed, its tasks must be migrated to a surviving display

The cross-display movement process:

```mermaid
sequenceDiagram
    participant Shell as WM Shell
    participant WOC as WindowOrganizerController
    participant TC as TransitionController
    participant Task as Task
    participant DC_Old as DisplayContent (old)
    participant DC_New as DisplayContent (new)
    participant SF as SurfaceFlinger

    Shell->>WOC: applyTransaction(reparent task to new display)
    WOC->>TC: createTransition(TRANSIT_CHANGE)
    TC->>Task: collect()

    WOC->>Task: reparent(newParent)
    Task->>DC_Old: removeChild(task)
    Task->>DC_New: addChild(task)

    Note over Task: Configuration updated<br/>(new display metrics,<br/>density, rotation)

    Task-->>TC: ready (redrawn)
    TC->>Shell: onTransitionReady(TransitionInfo)
    Shell->>SF: Animate surface movement
```

The `DisplayContent` class tracks several key settings that affect cross-display behavior:

- `mMinSizeOfResizeableTaskDp` -- Minimum task size on this display
- IME policy (`DISPLAY_IME_POLICY_LOCAL` vs `DISPLAY_IME_POLICY_FALLBACK_DISPLAY`) -- Whether the IME appears on this display or on the default display
- Display content mode management (enabled via `ENABLE_DISPLAY_CONTENT_MODE_MANAGEMENT` flag)

### 23.5.5 Per-Display Focus

The window system maintains focus at two levels:

1. **Per-display focus** -- Each `DisplayContent` tracks its own focused window
2. **Global focus** -- `RootWindowContainer` determines which display's focused window is the "top" focus (receives key events)

This dual-level system is essential for multi-display scenarios where the user might interact with different displays simultaneously (e.g., typing on one display while watching a video on another).

### 23.5.6 Display Groups and Topology

Displays can be organized into groups for coordinated behavior. Display groups affect:

- **Wallpaper sharing**: Displays in the same group may share wallpaper
- **Configuration inheritance**: Group-level configuration overrides
- **Focus behavior**: Focus policies may be group-aware

The display topology system manages spatial relationships between displays:

```mermaid
graph LR
    subgraph "Display Topology"
        D0["Display 0<br/>(Internal)<br/>1080x2400"]
        D1["Display 1<br/>(External HDMI)<br/>1920x1080"]
        D2["Display 2<br/>(Virtual - Cast)<br/>1280x720"]
    end

    D0 -->|"Right edge"| D1
    D0 -.->|"No spatial relation"| D2

    style D0 fill:#e8f5e9
    style D1 fill:#e1f5fe
    style D2 fill:#fff3e0
```

Spatial relationships enable:

- Cursor movement across adjacent display edges
- Drag-and-drop between displays
- Window drag-to-move between displays

### 23.5.7 IME Policy Per Display

Each display has an IME (Input Method Editor) policy that determines where the software keyboard appears:

```java
DISPLAY_IME_POLICY_LOCAL           // IME shows on this display
DISPLAY_IME_POLICY_FALLBACK_DISPLAY // IME shows on default display
```

The policy is cached in WMS at the volatile `mDisplayImePolicyCache` map for lock-free access. Virtual displays and some secondary displays use `FALLBACK_DISPLAY` policy because they may not have appropriate system decorations or touch input for IME interaction.

The `ImeContainer` within each `DisplayContent` manages the IME window's z-ordering. The IME needs special z-ordering logic because it must appear:

- Above the target window (the window requesting input)
- Below system overlays and the navigation bar
- In the correct position relative to the `DisplayArea` hierarchy

### 23.5.8 Display Configuration and Overrides

Each `DisplayContent` tracks both initial and overridden display metrics. These can be modified via:

- **adb shell**: `wm size`, `wm density`, `wm scaling` commands
- **Settings**: User-accessible display size/density settings
- **System server**: Programmatic display configuration changes

The override system maintains a ratio (`mForcedDisplayDensityRatio`) between the forced density and the initial density. When the display resolution changes (e.g., on a device with variable resolution support), this ratio is used to scale the density proportionally, preserving the user's chosen display size.

```java
// DisplayContent fields for override tracking
int mBaseDisplayWidth = 0;     // May differ from mInitialDisplayWidth
int mBaseDisplayHeight = 0;    // May differ from mInitialDisplayHeight
int mBaseDisplayDensity = 0;   // May differ from mInitialDisplayDensity
boolean mIsSizeForced = false;
boolean mIsDensityForced = false;
float mForcedDisplayDensityRatio = 0.0f;
```

### 23.5.9 Cross-Display Drag and Drop

A drag gesture is not confined to the display it started on. When a connected-display
setup forms a single topology (Section 23.5.6), the user can press on content on one
display, drag the shadow across the seam, and drop it on a window on another display.
The mechanics live entirely in WindowManager's `DragState` and `DragDropController`
(`frameworks/base/services/core/java/com/android/server/wm/`); the one drag surface
follows the pointer out of one display's surface hierarchy and into another's.

A drag starts in `DragDropController.performDrag()` (`DragDropController.java:162`),
which builds the drag `SurfaceControl`, parents it to the origin display's overlay
(`reparentToOverlay`, line 301), and records both the origin and the current display on
the `DragState`:

```java
// DragState.java
DisplayContent mStartDragDisplayContent;    // line 139 -- where the drag began
DisplayContent mCurrentDisplayContent;      // line 144 -- where the pointer is now
```

The drag's own input window is created `DISPLAY_TOPOLOGY_AWARE` (`DragState.java:445`),
which is what lets the pointer -- and therefore the drag -- leave the origin display at
all: input dispatch follows the display topology instead of clamping to one display's
bounds.

*How a drag surface follows the pointer onto another display*

```mermaid
flowchart TD
    EV["MotionEvent during drag<br/>getDisplayId() = D2"] --> RX["DragInputEventReceiver<br/>(DragInputEventReceiver.java:66)"]
    RX --> HM["DragDropController.handleMotionEvent(displayId=D2)<br/>(DragDropController.java:513)"]
    HM --> UP["DragState.updateDragSurfaceLocked()<br/>(DragState.java:725)"]
    UP --> Q{"current display != D2?"}
    Q -->|"no, same display"| MOVE["move shadow within display<br/>setPosition"]
    Q -->|"yes, crossed to D2"| CHK{"DisplayContent for D2 exists?"}
    CHK -->|"no"| ENDD["endDragLocked()"]
    CHK -->|"yes"| X["mCurrentDisplayContent = D2"]
    X --> RE["reparent shadow to D2.getSurfaceControl()<br/>(DragState.java:762)"]
    RE --> SC["rescale by density ratio<br/>D2 / D1 mBaseDisplayDensity"]
    SC --> IN["inputWindowHandle.displayId = D2<br/>(DragState.java:770)"]
    IN --> DROP["DRAG_LOCATION / DROP routed to<br/>windows on D2"]
    MOVE --> DROP
    style RE fill:#2196F3,color:#fff
    style IN fill:#4CAF50,color:#fff
```

Every drag motion event carries the display the pointer is currently over.
`DragInputEventReceiver` reads `motionEvent.getDisplayId()`
(`DragInputEventReceiver.java:66`) and forwards it to
`DragDropController.handleMotionEvent(keepHandling, displayId, x, y)`
(`DragDropController.java:513`), which calls `DragState.updateDragSurfaceLocked()`
(`DragState.java:725`). That method is where a display crossing is handled:

- **Detect the crossing.** It compares the incoming `displayId` with the current one
  (`if (mCurrentDisplayContent.mDisplayId != displayId)`, line 736); if the target
  `DisplayContent` no longer exists the drag ends, otherwise `mCurrentDisplayContent` is
  updated to the new display (line 745).
- **Re-parent the drag surface.** The shadow is moved into the new display's surface
  tree -- `mTransaction.reparent(mSurfaceControl, mCurrentDisplayContent.getSurfaceControl())`
  (line 762). This is the literal hand-off of the surface between displays.
- **Rescale for density.** Because two displays can differ in density, the animated
  scale and thumbnail offsets are multiplied by the ratio of the new display's
  `mBaseDisplayDensity` to the old one's (lines 756-761), so the shadow keeps the same
  physical size as it crosses (a 1.0 scale onto a 420-dpi panel from a 160-dpi one
  becomes about 2.6).
- **Redirect input.** The drag input window's `displayId` is updated and re-applied
  (`inputWindowHandle.displayId = displayId`, line 770) so subsequent dispatch and the
  `ACTION_DRAG_LOCATION` / `ACTION_DROP` events route to windows on the new display.

Windows learn about a drag through `broadcastDragStartedLocked()`, which walks *every*
window on *every* display (`mService.mRoot.forAllWindows(...)`), not just the origin
display's. One wrinkle is coordinates: `ACTION_DRAG_STARTED` carries window-relative
*pixel* coordinates, but there is no global pixel space across displays, only global dp.
So for a window on a different display from the drag origin, `sendDragStartedLocked()`
deliberately sends a sentinel position
(`new PointF(-newWin.getBounds().left - 1, -newWin.getBounds().top - 1)`,
`DragState.java:569`) that signals "the drag is off this display" without implying a real
distance; per-display `ACTION_DRAG_LOCATION` events, by contrast, carry valid
display-local coordinates.

Two further details complete the cross-display picture:

- **Return animation.** If a drag is released without being consumed and the pointer
  ended on a different display from where it began
  (`mCurrentDisplayContent.getDisplayId() != mStartDragDisplayContent.getDisplayId()`,
  `DragState.java:825`), the snap-back animation scales toward
  `DIFFERENT_DISPLAY_RETURN_ANIMATION_SCALE = 0.75f` (line 85) instead of animating a
  meaningless cross-display translation.
- **Topology changes mid-drag.** If displays are added, removed, or rearranged while a
  drag is in flight, `DragDropController.handleDisplayTopologyChange()`
  (`DragDropController.java:493`) cancels the drag outright, because the cached
  `DisplayContent`s could now be stale.

What is *not* gated is the destination display. `isValidDropTarget()` enforces the usual
window-level rules -- `DRAG_FLAG_GLOBAL` (cross-window), `DRAG_FLAG_GLOBAL_SAME_APPLICATION`
(same-UID only), URI-permission grants, and cross-profile copy restrictions -- but none of
them test whether the target window is on the *same display* as the source, so a drop is
allowed on any eligible window regardless of which display hosts it. Cross-display drag is
long-standing window-system behavior rather than an Android 17 addition; Android 17 leaves
the model unchanged.

---

## 23.6 Input System Integration

### 23.6.1 InputFlinger to WMS Pipeline

The input system and window system are tightly coupled: InputFlinger needs to know the window layout to route touch events to the correct window, and WMS needs to track focus for keyboard input routing.

```mermaid
graph LR
    subgraph "Kernel"
        EV["evdev<br/>(touch, keyboard)"]
    end

    subgraph "Native Services"
        IR["InputReader<br/>(read events)"]
        ID["InputDispatcher<br/>(route events)"]
    end

    subgraph "System Server"
        IMS["InputManagerService"]
        WMS["WindowManagerService"]
        IM["InputMonitor<br/>(per display)"]
    end

    subgraph "Application"
        IC["InputChannel"]
        VRI["ViewRootImpl"]
    end

    EV --> IR
    IR --> ID
    ID <-->|"window layout sync"| IM
    IM --> WMS
    IMS --> ID

    ID -->|"InputChannel<br/>(socket pair)"| IC
    IC --> VRI
```

### 23.6.2 InputMonitor

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/InputMonitor.java`

`InputMonitor` is instantiated per-display (`DisplayContent` creates one) and is responsible for updating InputFlinger with the current window layout. When windows change, `InputMonitor` walks the window hierarchy and builds an ordered list of `InputWindowHandle` structures that tell InputFlinger:

- The bounds of each window
- Whether it is touchable (`FLAG_NOT_TOUCHABLE`)
- Whether it is touch-modal (`FLAG_NOT_TOUCH_MODAL`)
- Whether it should receive input at all (`INPUT_FEATURE_NO_INPUT_CHANNEL`)
- The input channel to dispatch events through
- Trusted overlay status (`PRIVATE_FLAG_TRUSTED_OVERLAY`)
- SPY flag for input monitoring (`INPUT_FEATURE_SPY`)

Special input consumers are registered for system-level input interception:

```java
INPUT_CONSUMER_PIP              // PiP gesture handling
INPUT_CONSUMER_RECENTS_ANIMATION // Recents swipe gesture
INPUT_CONSUMER_WALLPAPER        // Wallpaper touch forwarding
```

### 23.6.3 Window Targeting

When a touch event arrives, InputDispatcher resolves the target window through these steps:

1. **Find the display**: Map the event coordinates to a display via display topology
2. **Walk the window list**: Top-to-bottom through the display's window list
3. **Hit test**: Check if the event coordinates fall within a window's touchable region
4. **Check flags**: Skip windows with `FLAG_NOT_TOUCHABLE`; pass through windows without `FLAG_NOT_TOUCH_MODAL`
5. **Trusted overlay check**: Special handling for trusted overlays that should intercept but not consume input
6. **Deliver**: Send the event through the window's `InputChannel`

For keyboard/key events, the dispatch is simpler: events go to the focused window (determined by `DisplayContent.mCurrentFocus`).

### 23.6.4 Focus Management

Focus management is a multi-step process triggered by `WindowManagerService.updateFocusedWindowLocked()`:

```java
static final int UPDATE_FOCUS_NORMAL = 0;
static final int UPDATE_FOCUS_WILL_ASSIGN_LAYERS = 1;
static final int UPDATE_FOCUS_PLACING_SURFACES = 2;
static final int UPDATE_FOCUS_WILL_PLACE_SURFACES = 3;
static final int UPDATE_FOCUS_REMOVING_FOCUS = 4;
```

The five modes control when during the surface placement cycle focus is updated:

| Mode | When Used | Behavior |
|------|-----------|----------|
| `UPDATE_FOCUS_NORMAL` | General focus update | Triggers layout redo if focus changed |
| `UPDATE_FOCUS_WILL_ASSIGN_LAYERS` | Before layer assignment | Layers assigned after focus update |
| `UPDATE_FOCUS_PLACING_SURFACES` | During surface placement | Layout already in progress |
| `UPDATE_FOCUS_WILL_PLACE_SURFACES` | Layout will follow | Defers layout to upcoming pass |
| `UPDATE_FOCUS_REMOVING_FOCUS` | Focus window being removed | Cleans up outgoing focus |

Focus is determined by walking the window hierarchy top-to-bottom and finding the first window that:

- Is visible (or becoming visible)
- Is focusable (not `FLAG_NOT_FOCUSABLE`)
- Is not behind the keyguard (unless `FLAG_SHOW_WHEN_LOCKED`)
- Has the `mIsFocusable` property set (not explicitly unfocusable)

### 23.6.5 Input and Display Topology

For multi-display scenarios, the input system must handle display topology -- knowing which displays are adjacent and how to route events that cross display boundaries. `DisplayContent` maintains:

```java
private SurfaceControl mInputOverlayLayer;
private SurfaceControl mPointerEventDispatcherOverlayLayer;
```

The `INPUT_FEATURE_DISPLAY_TOPOLOGY_AWARE` flag on a window's layout params indicates that it should receive input events with display topology awareness, enabling seamless cursor movement across displays.

### 23.6.6 InputChannel: The Event Delivery Mechanism

`InputChannel` is a pair of Unix domain sockets that connects InputDispatcher (native) to the application's `ViewRootImpl` (Java). Each `WindowState` that can receive input gets an `InputChannel`:

```mermaid
graph LR
    subgraph "Native (InputDispatcher)"
        ID["InputDispatcher"]
        SC_S["Server socket"]
    end

    subgraph "Application Process"
        SC_C["Client socket"]
        IER["InputEventReceiver"]
        VRI["ViewRootImpl"]
    end

    ID --> SC_S
    SC_S <-->|"Unix socket pair"| SC_C
    SC_C --> IER
    IER --> VRI
```

The socket pair is created during `addWindow()` and the server-side socket is registered with `InputDispatcher` via the `InputWindowHandle`. The client-side socket is returned to the application through the `IWindowSession`.

Events flow as serialized `InputMessage` structures through the socket. The application reads them in its `InputEventReceiver` (attached to the Looper), processes them through the `ViewRootImpl` InputStage chain, and sends a finished signal back through the socket.

### 23.6.7 Window Input Flags

Window input behavior is controlled by several flags:

| Flag | Effect |
|------|--------|
| `FLAG_NOT_FOCUSABLE` | Window cannot receive keyboard focus |
| `FLAG_NOT_TOUCHABLE` | Touch events pass through this window |
| `FLAG_NOT_TOUCH_MODAL` | Touch events outside window bounds pass to windows behind |
| `FLAG_SLIPPERY` | Touch can slip to adjacent windows |
| `INPUT_FEATURE_NO_INPUT_CHANNEL` | Window has no input channel (invisible to input) |
| `INPUT_FEATURE_SPY` | Window receives copies of all input events (monitoring) |
| `INPUT_FEATURE_SENSITIVE_FOR_PRIVACY` | Window content is privacy-sensitive |
| `INPUT_FEATURE_DISPLAY_TOPOLOGY_AWARE` | Handles cross-display pointer movement |
| `PRIVATE_FLAG_TRUSTED_OVERLAY` | Overlay is trusted (system-signed) |

The `FLAG_NOT_TOUCH_MODAL` flag is particularly important for multi-window scenarios: without it, a window would consume all touch events within the display bounds, even those outside the window's visible area.

### 23.6.8 Input Consumers

WMS can register special "input consumers" that intercept input before it reaches normal windows:

```java
INPUT_CONSUMER_PIP              // Intercepts gestures for PiP manipulation
INPUT_CONSUMER_RECENTS_ANIMATION // Intercepts swipe-up for recents gesture
INPUT_CONSUMER_WALLPAPER        // Forwards touch to wallpaper for parallax
```

Input consumers are implemented as `InputConsumerImpl` objects that have their own `InputChannel` and `SurfaceControl`. They are inserted into the input window list at specific z-order positions to intercept events before they reach app windows.

### 23.6.9 Spy Windows

The `INPUT_FEATURE_SPY` flag allows a window to receive copies of input events without consuming them. This is used by:

- System gestures (edge swipe detection)
- Accessibility overlays
- Input monitoring for analytics

Spy windows do not affect event dispatch to normal windows -- they only observe.

### 23.6.10 Cursor and Touch Sprites (libinputservice)

Sections 23.6.1–23.6.9 trace input events from kernel evdev all the way
into `ViewRootImpl`'s `InputStage` chain. None of those subsystems draw
anything — they route events. The visible artefacts that follow the
pointer around (the mouse cursor arrow, the white circles that appear
under fingertips when "Show touches" is enabled in developer options,
the stylus tip indicator) are drawn by a separate library at
`frameworks/base/libs/input/`, packaged as `libinputservice`. This
subsection covers what that library does, where it lives in the
process tree, and how it interacts with InputFlinger and SurfaceFlinger.

#### Why a Separate Library

InputFlinger lives in its own native daemon and is performance-critical;
it must not pull in `libhwui`, `libgui`, or any other heavy graphics
dependency. But the pointer policy (which cursor to show, whether to
fade, how to animate touch spots) has to *render*. The split is
intentional:

- InputFlinger defines an abstract
  `PointerControllerInterface` (in
  `frameworks/native/services/inputflinger/include/`).
- A separate library, `libinputservice`, provides the concrete
  implementation. The header that wires the two together explicitly
  documents the dependency story:

```cpp
// Source: frameworks/native/services/inputflinger/include/
//   PointerChoreographerPolicyInterface.h
// "library, libinputservice, that has the additional dependencies. The PointerController
//  will be mocked when testing PointerChoreographer."
virtual std::shared_ptr<PointerControllerInterface> createPointerController(
        PointerControllerInterface::ControllerType type) = 0;
```

- The factory call is made by `PointerChoreographerPolicyInterface`, an
  interface that *system_server* implements via its JNI native side.
  `frameworks/base/services/core/jni/Android.bp` (line 142) links
  `libinputservice` into the JNI bundle, so the concrete
  `PointerController` is constructed inside the `system_server`
  process, not inside InputFlinger.

Net effect: the heavy graphics dependencies stay out of the InputFlinger
binary; InputFlinger holds an opaque `PointerControllerInterface*` and
calls `move(...)`, `setPosition(...)`, `setSpots(...)`,
`updatePointerIcon(...)` on it without knowing those calls eventually
schedule SurfaceFlinger transactions.

#### What's in the Library

The shared library is ~10 files in `frameworks/base/libs/input/`:

| File | Purpose |
|------|---------|
| `PointerController.{h,cpp}` | Concrete `PointerControllerInterface` implementation; per-display sprite owner |
| `PointerControllerContext.{h,cpp}` | Per-pointer-controller shared state (policy, looper, sprite controller, message handler) |
| `MouseCursorController.{h,cpp}` | Manages the single mouse-cursor sprite per display: position, icon style, fade animation |
| `TouchSpotController.{h,cpp}` | Manages up to 12 "spot" sprites per display (one per active finger) |
| `SpriteController.{h,cpp}` | Generic Sprite/SpriteController abstraction over `SurfaceComposerClient` |
| `SpriteIcon.{h,cpp}` | Bitmap + hotspot pair drawn into a sprite surface |

The library compiles as `cc_library_shared` with the
`inputflinger_defaults` build flags, so InputFlinger code shape stays
consistent across the two binaries. Its dependency list is the give-away:

```blueprint
// Source: frameworks/base/libs/input/Android.bp:34
shared_libs: [
    "libandroid_runtime",
    "libbinder",
    "libcutils",
    "libhwui",       // graphics
    "liblog",
    "libutils",
    "libgui",        // SurfaceComposerClient
    "libinput",
],
header_libs: [
    "libinputflinger_headers",
],
```

`libhwui` and `libgui` are the dependencies InputFlinger cannot afford
to take.

#### The Three Sprite Roles

`PointerController` has three concrete subclasses, each of which
*disables* the operations that do not apply to its role by fatal-asserting:

```cpp
// Source: frameworks/base/libs/input/PointerController.h:143
class MousePointerController : public PointerController {
    // disables setPresentation(), setSpots(), clearSpots()
    // — mouse pointers never use spot rendering
};

class TouchPointerController : public PointerController {
    // disables move(), setPosition(), getPosition(), fade(), unfade(), ...
    // — touch spots are coordinate-driven, not delta-driven; no fade
};

class StylusPointerController : public PointerController {
    // disables setPresentation(), setSpots(), clearSpots()
    // — stylus is a single tip indicator
};
```

The fatal-assert pattern (`LOG_ALWAYS_FATAL("Should not be called")`) is
deliberate: misuse from upstream code crashes
loudly in CI rather than silently rendering the wrong thing on the
screen. Each role has exactly one valid call path, and the type system
ensures InputFlinger can't accidentally ask a touch controller to
`move(...)` a cursor.

The shared base class holds:

- A `MouseCursorController` (single cursor per pointer controller)
- A per-display map `unordered_map<LogicalDisplayId, TouchSpotController>`
  (lazy-created spot controllers, one per display that has active
  touches)
- A `DisplayInfoListener` registered with `WindowInfosListener` to
  receive cross-display topology changes

#### Sprite Lifecycle

`SpriteController` is the heart of the rendering. Each `Sprite` is
backed by a `SurfaceControl` parented under a "system sprite overlay
layer" provided by SurfaceFlinger. The overlay layer sits at a
z-order chosen by SurfaceFlinger to be on top of every window — that
is what makes the cursor always visible, even over `TYPE_SYSTEM_ALERT`
windows.

```mermaid
sequenceDiagram
    participant IF as InputFlinger<br/>(PointerChoreographer)
    participant SS as system_server<br/>(JNI policy)
    participant PC as PointerController<br/>(libinputservice)
    participant SC as SpriteController
    participant SF as SurfaceFlinger

    IF->>SS: createPointerController(MOUSE)
    SS->>PC: PointerController::create(policy, looper, spriteController, MOUSE)
    PC->>PC: build MouseCursorController, register WindowInfosListener
    Note over PC: cursor sprite created lazily on first setIcon()
    IF->>PC: move(dx, dy) on each mouse event
    PC->>PC: clamp to displayViewport, apply Transform
    PC->>SC: setPosition(sprite, x, y) — under controller's lock
    SC->>SC: invalidateSpriteLocked(sprite) + post MSG_UPDATE_SPRITES
    SC->>SC: doUpdateSprites() on looper thread
    SC->>SF: SurfaceComposerClient transaction (setPosition, setLayer)
    SF-->>SC: next vsync renders sprite at new position
```

Two layered design choices stand out:

- **All public setters acquire the controller's lock, but the surface
  work is asynchronous.** `Sprite::setPosition(...)` updates a local
  `SpriteState` field, marks a `DIRTY_POSITION` bit, and posts a
  message to the controller's `Handler`. The actual
  `SurfaceComposerClient` transaction runs on a separate looper
  thread, so the input hot path is never blocked on SurfaceFlinger
  Binder round-trips.
- **`SpriteState` is copy-able.** The looper-thread update path
  *copies* the locked state out, releases the lock, and then runs the
  transaction. Resizing or redrawing a sprite surface cannot stall an
  input thread, even briefly. The comment in `SpriteController.h:170`
  spells this out: "the surfaces can be resized and redrawn without
  blocking the client by holding a lock on the sprites for a long
  time".

#### Touch Spot Specifics

`TouchSpotController` owns up to `MAX_SPOTS = 12` `Spot` records, each
tied to a finger pointer ID. When "Show touches" is on (Developer
Options → `SHOW_TOUCHES`), `PointerController::setSpots(...)` receives
the current `PointerCoords` array plus a `BitSet32` of active IDs:

```cpp
// Source: frameworks/base/libs/input/PointerController.h:64
void setSpots(const PointerCoords* spotCoords, const uint32_t* spotIdToIndex,
              BitSet32 spotIdBits, ui::LogicalDisplayId displayId) override;
```

The implementation:

1. Looks up the per-display `TouchSpotController` (creating one on
   first use).
2. For each bit in `spotIdBits`, either updates an existing `Spot` or
   adopts one from a recycled pool (the controller caches up to 12
   sprite SurfaceControls to avoid Binder round-trips when the same
   finger ID reappears).
3. Calls `Spot::updateSprite(...)` which sets icon / position / alpha
   on the underlying `Sprite`.
4. Spots not present in the new bitmask fade out and are recycled.

The `skipScreenshot` flag passed alongside spots adds
`ISurfaceComposerClient::eSkipScreenshot` to the sprite's
SurfaceControl flags, so screenshots and screen mirroring don't
capture the touch indicators (privacy + cleanliness for screencasts).

#### Display Topology Awareness

`PointerController` registers a `DisplayInfoListener` (subclass of
`WindowInfosListener`). When the window infos snapshot changes (a
display rotates, a virtual display appears, an external monitor's
viewport shifts), the listener fires `onDisplayInfosChangedLocked(...)`,
which:

- Updates the per-display `Transform` used to convert pointer
  coordinates from physical to logical display space.
- Rebuilds the spot-controller map to drop entries for displays that
  no longer exist.
- Updates `displaysToSkipScreenshot` so spot sprites stay
  screenshot-skipped on the right displays after topology changes.

The lock used by the listener is the same lock the controller uses
internally — the constructor comment in `PointerController.h:102`
explains the choice: the listener can outlive the controller (because
the `WindowInfosListener` registration takes a strong reference), so
sharing the listener's lock with the controller avoids needing a
separate lock with the same ordering rules.

#### Skip-Screenshot Per Display

`setSkipScreenshotFlagForDisplay(LogicalDisplayId)` /
`clearSkipScreenshotFlags()` let the system request that the *cursor*
also be excluded from screenshots / mirror feeds on specific displays.
This is used for screenrecord and projection scenarios where the
cursor would otherwise appear as a stale artefact in the captured
output. The flag flows through `MouseCursorController` down to
`Sprite::setSkipScreenshot(bool)` and then into the sprite's
`SurfaceControl` flags via the same async transaction path.

#### Summary: Why This Library Exists at This Boundary

The sprite layer is one of the cleanest examples in AOSP of *splitting
a subsystem along its dependency profile*:

- InputFlinger gets to remain a tight, dependency-light daemon focused
  on event delivery.
- The pointer/spot rendering policy gets to live in
  `system_server`, where it can talk to SurfaceFlinger, load icon
  bitmaps via the framework's resource system, and respect window
  topology changes.
- The seam between them (`PointerControllerInterface` +
  `PointerChoreographerPolicyInterface`) is small enough that
  InputFlinger unit tests mock it trivially, while still giving
  `system_server` complete control over what actually appears on
  screen.

For most callers, `libinputservice` is invisible — its surface is
"the cursor follows my mouse and the touch dots appear when developer
options are on". For framework developers tracing why the cursor
flickers, fades, or appears on the wrong display, `PointerController`
and its `MouseCursorController` / `TouchSpotController` collaborators
are where the answer lives.

---

## 23.7 Surface and Leash

### 23.7.1 The SurfaceControl Hierarchy

Every `WindowContainer` in the WM hierarchy has a corresponding `SurfaceControl` in SurfaceFlinger. This creates a parallel tree:

```mermaid
graph TB
    subgraph "WM Hierarchy (Java)"
        RWC_J["RootWindowContainer"]
        DC_J["DisplayContent"]
        DA_J["DisplayArea"]
        TDA_J["TaskDisplayArea"]
        T_J["Task"]
        AR_J["ActivityRecord"]
        WS_J["WindowState"]
    end

    subgraph "Surface Hierarchy (SurfaceFlinger)"
        RWC_S["SurfaceControl<br/>(root)"]
        DC_S["SurfaceControl<br/>(display)"]
        DA_S["SurfaceControl<br/>(display area)"]
        TDA_S["SurfaceControl<br/>(task display area)"]
        T_S["SurfaceControl<br/>(task)"]
        AR_S["SurfaceControl<br/>(activity)"]
        WS_S["SurfaceControl<br/>(window buffer layer)"]
    end

    RWC_J -.->|"1:1"| RWC_S
    DC_J -.->|"1:1"| DC_S
    DA_J -.->|"1:1"| DA_S
    TDA_J -.->|"1:1"| TDA_S
    T_J -.->|"1:1"| T_S
    AR_J -.->|"1:1"| AR_S
    WS_J -.->|"1:1"| WS_S

    RWC_S --> DC_S
    DC_S --> DA_S
    DA_S --> TDA_S
    TDA_S --> T_S
    T_S --> AR_S
    AR_S --> WS_S
```

This 1:1 mapping is a fundamental invariant of the system. Every time a child is added to or removed from a `WindowContainer`, a corresponding `SurfaceControl` reparent operation is issued to SurfaceFlinger via a `SurfaceControl.Transaction`.

The `prepareSurfaces()` method, called during the surface placement pass, allows each `WindowContainer` to update its `SurfaceControl` properties (position, size, alpha, visibility, layer order) before the transaction is committed.

### 23.7.2 Animation Leash Mechanism

The animation leash is the key mechanism that enables smooth animations of window containers. The `SurfaceAnimator` class manages this:

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/SurfaceAnimator.java` (about 640 lines)

From the source Javadoc:

> *"We do this by reparenting all child surfaces of an object onto a new surface, called the 'Leash'. The Leash gets attached in the surface hierarchy where the children were attached to. We then hand off the Leash to the component handling the animation. When the animation is done, our callback to finish the animation will be invoked, at which we reparent the children back to the original parent."*

```mermaid
graph TB
    subgraph "Before Animation"
        P1["Parent SurfaceControl"]
        C1["Container SurfaceControl"]
        CH1["Child Surface A"]
        CH2["Child Surface B"]
        P1 --> C1
        C1 --> CH1
        C1 --> CH2
    end

    subgraph "During Animation"
        P2["Parent SurfaceControl"]
        L2["LEASH SurfaceControl<br/>(animation target)"]
        C2["Container SurfaceControl"]
        CH3["Child Surface A"]
        CH4["Child Surface B"]
        P2 --> L2
        L2 --> C2
        C2 --> CH3
        C2 --> CH4
    end

    subgraph "After Animation"
        P3["Parent SurfaceControl"]
        C3["Container SurfaceControl"]
        CH5["Child Surface A"]
        CH6["Child Surface B"]
        P3 --> C3
        C3 --> CH5
        C3 --> CH6
    end

    style L2 fill:#fff3e0
```

The leash creation flow:

```java
void startAnimation(Transaction t, AnimationAdapter anim, boolean hidden,
        @AnimationType int type, ...) {
    cancelAnimation(t, true /* restarting */, true /* forwardCancel */);
    mAnimation = anim;
    mAnimationType = type;
    SurfaceControl surface = mAnimatable.getSurfaceControl();
    if (mLeash == null) {
        mLeash = createAnimationLeash(mAnimatable, surface, t, type,
                mAnimatable.getSurfaceWidth(), mAnimatable.getSurfaceHeight(),
                0, 0, hidden, mService.mTransactionFactory);
        mAnimatable.onAnimationLeashCreated(t, mLeash);
    }
    mAnimatable.onLeashAnimationStarting(t, mLeash);
    mAnimation.startAnimation(mLeash, t, type, mInnerAnimationFinishedCallback);
}
```

### 23.7.3 Animation Types

The `SurfaceAnimator` defines animation types that categorize different uses of the leash mechanism:

```java
ANIMATION_TYPE_NONE           = 0;       // No animation
ANIMATION_TYPE_APP_TRANSITION = 1;       // App open/close/change
ANIMATION_TYPE_SCREEN_ROTATION = 1 << 1; // Screen rotation
ANIMATION_TYPE_DIMMER         = 1 << 2;  // Background dimming
ANIMATION_TYPE_RECENTS        = 1 << 3;  // Recents gesture
ANIMATION_TYPE_WINDOW_ANIMATION = 1 << 4; // Per-window animation
ANIMATION_TYPE_INSETS_CONTROL = 1 << 5;  // Insets show/hide
ANIMATION_TYPE_TOKEN_TRANSFORM = 1 << 6; // Fixed rotation
ANIMATION_TYPE_STARTING_REVEAL = 1 << 7; // Starting window reveal
ANIMATION_TYPE_PREDICT_BACK   = 1 << 8;  // Predictive back gesture
ANIMATION_TYPE_ALL            = -1;      // Match any type
```

These are bit flags, enabling queries like "is any animation of type X running on this container or its children?"

### 23.7.4 Layer Assignment and Leash Interaction

When a leash is present, layer operations must target the leash rather than the underlying surface. `SurfaceAnimator` handles this transparently:

```java
void setLayer(Transaction t, int layer) {
    t.setLayer(mLeash != null ? mLeash : mAnimatable.getSurfaceControl(), layer);
}

void setRelativeLayer(Transaction t, SurfaceControl relativeTo, int layer) {
    t.setRelativeLayer(mLeash != null ? mLeash : mAnimatable.getSurfaceControl(),
            relativeTo, layer);
}
```

### 23.7.5 Animation Transfer

Animations can be transferred between `SurfaceAnimator` instances without visual interruption. This is used when a window is reparented during an active animation:

```java
void transferAnimation(SurfaceAnimator from) {
    // Steal the leash, animation, and callbacks from the source
    mLeash = from.mLeash;
    mAnimation = from.mAnimation;
    mAnimationType = from.mAnimationType;
    mSurfaceAnimationFinishedCallback = from.mSurfaceAnimationFinishedCallback;

    // Cancel source without forwarding to the animation adapter
    from.cancelAnimation(t, false, false /* forwardCancel */);

    // Reparent our surface to the stolen leash
    t.reparent(surface, mLeash);
    t.reparent(mLeash, parent);

    // Register in the transfer map for callback routing
    mService.mAnimationTransferMap.put(mAnimation, this);
}
```

The `mAnimationTransferMap` in `WindowManagerService` ensures that when the animation adapter fires its completion callback, it is routed to the correct (new) `SurfaceAnimator` rather than the original.

### 23.7.6 The Animatable Interface

The `SurfaceAnimator.Animatable` interface defines the contract that any animatable container must implement:

```java
interface Animatable {
    // The transaction that will be used for pending surface operations
    Transaction getPendingTransaction();
    Transaction getSyncTransaction();
    void commitPendingTransaction();

    // Surface control management
    SurfaceControl getSurfaceControl();
    SurfaceControl getAnimationLeashParent();
    SurfaceControl getParentSurfaceControl();

    // Surface dimensions
    int getSurfaceWidth();
    int getSurfaceHeight();

    // Leash lifecycle callbacks
    void onAnimationLeashCreated(Transaction t, SurfaceControl leash);
    void onAnimationLeashLost(Transaction t);
    void onLeashAnimationStarting(Transaction t, SurfaceControl leash);

    // Builder for creating the leash surface
    Builder makeAnimationLeash();
}
```

`WindowContainer` implements `Animatable`, which means every node in the hierarchy can be animated via the leash mechanism. This is used for:

- App transitions (open, close, change)
- Window animations (enter, exit)
- Screen rotation
- Insets animations (status bar hide/show)
- Recents gesture animation
- Predictive back gesture

### 23.7.7 Leash Creation Details

The `createAnimationLeash()` static method in `SurfaceAnimator` constructs the leash surface:

```java
static SurfaceControl createAnimationLeash(Animatable animatable,
        SurfaceControl surface, Transaction t, @AnimationType int type,
        int width, int height, int x, int y, boolean hidden,
        Supplier<Transaction> transactionFactory) {

    SurfaceControl leash = animatable.makeAnimationLeash()
            .setName(surface + " - animation-leash of " + typeToString(type))
            .setHidden(hidden)
            .setEffectLayer()
            .setCallsite("SurfaceAnimator.createAnimationLeash")
            .build();

    // Reparent the leash to where the surface was
    t.reparent(leash, animatable.getAnimationLeashParent());
    // Reparent the surface under the leash
    t.reparent(surface, leash);
    // Position and size the leash
    t.setPosition(leash, x, y);
    t.setWindowCrop(leash, width, height);
    // Transfer layer assignment
    t.setAlpha(leash, hidden ? 0 : 1);

    return leash;
}
```

The leash is created as an `EffectLayer` (a container-only surface with no buffer), which means it does not consume GPU memory or affect composition performance -- it only provides a transform node in the surface tree.

### 23.7.8 Transaction Batching and Atomic Apply

All surface changes during a placement cycle are accumulated into a single `SurfaceControl.Transaction` and applied atomically:

```mermaid
sequenceDiagram
    participant WMS as WindowManagerService
    participant WC as WindowContainers
    participant TX as SurfaceControl.Transaction
    participant SF as SurfaceFlinger

    WMS->>WC: performSurfacePlacement()
    loop For each container
        WC->>TX: setPosition(...)
        WC->>TX: setLayer(...)
        WC->>TX: setVisibility(...)
        WC->>TX: setCrop(...)
        WC->>TX: setAlpha(...)
        WC->>TX: setMatrix(...)
    end

    WMS->>TX: apply()
    TX->>SF: Atomic transaction commit
    Note over SF: All changes visible<br/>in a single frame
```

This atomic commit ensures that users never see intermediate states where some windows have moved but others have not. The atomicity is guaranteed by SurfaceFlinger's transaction system, which processes all operations in a single commit before the next frame.

### 23.7.9 Sync Transaction vs Pending Transaction

`WindowContainer` maintains two transaction objects with different semantics:

- **`mPendingTransaction`** (`getPendingTransaction()`): Accumulated changes that will be applied during the next `performSurfacePlacement()`. This is the normal path for layout changes.

- **`mSyncTransaction`** (`getSyncTransaction()`): Used during BLAST sync. When a container is part of a sync group, its surface changes are redirected to the sync transaction, which is held until all participants are ready, then applied atomically with the synced buffer deliveries.

The distinction is critical for transitions: during a transition, participants redirect their surface changes to the sync transaction so that the visual update (surfaces move) is synchronized with the content update (surfaces show new content).

---

## 23.8 Window Types and Z-Order

### 23.8.1 Window Type Ranges

Android organizes window types into three ranges, defined in `WindowManager.LayoutParams`:

**Source file:** `frameworks/base/core/java/android/view/WindowManager.java`

```java
// Application windows: 1-99
public static final int FIRST_APPLICATION_WINDOW = 1;
public static final int LAST_APPLICATION_WINDOW  = 99;

// Sub-windows (attached to an application window): 1000-1999
public static final int FIRST_SUB_WINDOW = 1000;
public static final int LAST_SUB_WINDOW  = 1999;

// System windows (special purpose): 2000-2999
public static final int FIRST_SYSTEM_WINDOW = 2000;
public static final int LAST_SYSTEM_WINDOW  = 2999;
```

### 23.8.2 Application Window Types

| Constant | Value | Description |
|----------|-------|-------------|
| `TYPE_BASE_APPLICATION` | 1 | Base window for an activity |
| `TYPE_APPLICATION` | 2 | Normal application window |
| `TYPE_APPLICATION_STARTING` | 3 | Starting/splash screen window |
| `TYPE_DRAWN_APPLICATION` | 4 | Variant that waits for first draw |
| `TYPE_APPLICATION_OVERLAY` | 2038 | App overlay (needs SYSTEM_ALERT_WINDOW) |

Application windows (1-99) are the most common. The `TYPE_BASE_APPLICATION` is created automatically for each `ActivityRecord`.

### 23.8.3 Sub-Window Types

| Constant | Value | Description |
|----------|-------|-------------|
| `TYPE_APPLICATION_PANEL` | 1000 | Panel on top of application |
| `TYPE_APPLICATION_MEDIA` | 1001 | Media surface (e.g., video) |
| `TYPE_APPLICATION_SUB_PANEL` | 1002 | Sub-panel |
| `TYPE_APPLICATION_ATTACHED_DIALOG` | 1003 | Dialog attached to app |
| `TYPE_APPLICATION_MEDIA_OVERLAY` | 1004 | Media overlay |
| `TYPE_APPLICATION_ABOVE_SUB_PANEL` | 1005 | Above sub-panel |

Sub-windows are children of an application window in the `WindowState` hierarchy. They are z-ordered relative to their parent.

### 23.8.4 System Window Types

System windows form the largest category. They are ordered by type value, which maps to relative z-order:

| Constant | Offset | Description |
|----------|--------|-------------|
| `TYPE_STATUS_BAR` | +0 | Status bar |
| `TYPE_SEARCH_BAR` | +1 | Search bar |
| `TYPE_PHONE` | +2 | Phone call window |
| `TYPE_SYSTEM_ALERT` | +3 | System alert dialog |
| `TYPE_KEYGUARD` | +4 | Keyguard (deprecated) |
| `TYPE_TOAST` | +5 | Toast notification |
| `TYPE_SYSTEM_OVERLAY` | +6 | System overlay |
| `TYPE_PRIORITY_PHONE` | +7 | Priority phone call |
| `TYPE_SYSTEM_DIALOG` | +8 | System dialog |
| `TYPE_KEYGUARD_DIALOG` | +9 | Keyguard dialog |
| `TYPE_SYSTEM_ERROR` | +10 | System error |
| `TYPE_INPUT_METHOD` | +11 | Input method (keyboard) |
| `TYPE_INPUT_METHOD_DIALOG` | +12 | IME candidate picker |
| `TYPE_WALLPAPER` | +13 | Wallpaper |
| `TYPE_STATUS_BAR_PANEL` | +14 | Status bar panel |
| `TYPE_SECURE_SYSTEM_OVERLAY` | +15 | Secure overlay |
| `TYPE_DRAG` | +16 | Drag surface |
| `TYPE_STATUS_BAR_SUB_PANEL` | +17 | Status bar sub-panel |
| `TYPE_POINTER` | +18 | Pointer |
| `TYPE_NAVIGATION_BAR` | +19 | Navigation bar |
| `TYPE_VOLUME_OVERLAY` | +20 | Volume control |
| `TYPE_BOOT_PROGRESS` | +21 | Boot progress |
| `TYPE_INPUT_CONSUMER` | +22 | Input consumer |
| `TYPE_NAVIGATION_BAR_PANEL` | +24 | Navigation bar panel |
| `TYPE_DISPLAY_OVERLAY` | +26 | Display overlay |
| `TYPE_MAGNIFICATION_OVERLAY` | +27 | Magnification overlay |
| `TYPE_PRIVATE_PRESENTATION` | +30 | Private presentation |
| `TYPE_VOICE_INTERACTION` | +31 | Voice interaction |
| `TYPE_ACCESSIBILITY_OVERLAY` | +32 | Accessibility overlay |
| `TYPE_VOICE_INTERACTION_STARTING` | +33 | Voice interaction starting |
| `TYPE_DOCK_DIVIDER` | +34 | Split-screen divider |
| `TYPE_QS_DIALOG` | +35 | Quick settings dialog |
| `TYPE_SCREENSHOT` | +36 | Screenshot window |
| `TYPE_PRESENTATION` | +37 | Presentation display |
| `TYPE_APPLICATION_OVERLAY` | +38 | Application overlay |
| `TYPE_ACCESSIBILITY_MAGNIFICATION_OVERLAY` | +39 | Accessibility magnification |
| `TYPE_NOTIFICATION_SHADE` | +40 | Notification shade |
| `TYPE_STATUS_BAR_ADDITIONAL` | +41 | Additional status bar |

### 23.8.5 Z-Order Layer Assignment

The `DisplayAreaPolicy` framework organizes windows into `DisplayArea` zones based on their type. Within each zone, layer assignment follows the `TYPE_LAYER_MULTIPLIER` system:

**Source file:** `frameworks/base/core/java/android/view/WindowManagerPolicyConstants.java`

```java
int TYPE_LAYER_MULTIPLIER = 10000;  // Layer spacing between types
int TYPE_LAYER_OFFSET     = 1000;   // Sub-layer offset within a type

int WATERMARK_LAYER       = TYPE_LAYER_MULTIPLIER * 100;
int STRICT_MODE_LAYER     = TYPE_LAYER_MULTIPLIER * 101;
int WINDOW_FREEZE_LAYER   = TYPE_LAYER_MULTIPLIER * 200;
int SCREEN_FREEZE_LAYER_BASE = WINDOW_FREEZE_LAYER + TYPE_LAYER_MULTIPLIER;
```

Each window type gets a base layer of `type * TYPE_LAYER_MULTIPLIER`, with `TYPE_LAYER_OFFSET` providing room for sub-windows within that type. This guarantees that system windows (type 2000+) are always above application windows (type 1-99) in the z-order.

### 23.8.6 DisplayArea-Based Z-Ordering

The modern z-ordering system uses `DisplayArea` hierarchy rather than raw layer numbers. The `DisplayAreaPolicy.DefaultProvider` builds a hierarchy that groups windows by feature:

```mermaid
graph TB
    ROOT["DisplayArea.Root<br/>(z-order root)"]

    subgraph "Below Apps"
        WALL["Wallpaper (TYPE_WALLPAPER)"]
    end

    subgraph "App Zone"
        HCT["HideDisplayCutout"]
        OH["OneHanded"]
        MAG["Magnification"]
        AZO["AppZoomOut"]
        TDA["DefaultTaskDisplayArea<br/>(all app tasks here)"]
    end

    subgraph "Above Apps"
        SBAR["StatusBar (TYPE_STATUS_BAR)"]
        NAV["NavigationBar (TYPE_NAVIGATION_BAR)"]
        IME["ImeContainer (TYPE_INPUT_METHOD)"]
        SHADE["NotificationShade (TYPE_NOTIFICATION_SHADE)"]
    end

    subgraph "Overlay Zone"
        ACC["AccessibilityOverlay"]
        MGOV["MagnificationOverlay"]
    end

    ROOT --> WALL
    ROOT --> HCT
    HCT --> OH
    OH --> MAG
    MAG --> TDA
    MAG --> AZO
    ROOT --> SBAR
    ROOT --> NAV
    ROOT --> IME
    ROOT --> SHADE
    ROOT --> ACC
    ROOT --> MGOV
```

Features like `FEATURE_HIDE_DISPLAY_CUTOUT`, `FEATURE_ONE_HANDED`, and `FEATURE_FULLSCREEN_MAGNIFICATION` are implemented as `DisplayArea` nodes that wrap sections of the hierarchy. When a feature is active, it transforms all surfaces in its subtree (e.g., `OneHanded` translates the entire app zone downward).

### 23.8.7 DisplayAreaPolicy and DisplayAreaPolicyBuilder

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/DisplayAreaPolicy.java`

`DisplayAreaPolicy` is an abstract class that defines how the `DisplayArea` hierarchy is constructed for a display:

```java
public abstract class DisplayAreaPolicy {
    protected final WindowManagerService mWmService;
    protected final RootDisplayArea mRoot;

    // Attach a WindowToken to the appropriate DisplayArea
    public abstract void addWindow(WindowToken token);

    // Find the DisplayArea for a given window type
    public abstract DisplayArea.Tokens findAreaForWindowType(int type,
            Bundle options, boolean ownerCanManageAppTokens,
            boolean roundedCornerOverlay);

    // Get DisplayAreas for a given feature
    public abstract List<DisplayArea<? extends WindowContainer>>
            getDisplayAreas(int featureId);
}
```

The `DisplayAreaPolicyBuilder` constructs the hierarchy using a feature-based approach:

```java
// Feature IDs from DisplayAreaOrganizer
FEATURE_DEFAULT_TASK_CONTAINER = 1;   // Where apps go
FEATURE_WINDOWED_MAGNIFICATION = 4;   // Windowed magnification
FEATURE_FULLSCREEN_MAGNIFICATION = 5; // Fullscreen magnification
FEATURE_ONE_HANDED = 6;               // One-handed mode
FEATURE_HIDE_DISPLAY_CUTOUT = 7;      // Display cutout hiding
FEATURE_IME_PLACEHOLDER = 8;          // IME positioning
FEATURE_APP_ZOOM_OUT = 9;             // App zoom out
```

Features are configured in the policy by specifying which window types they apply to. The builder then generates a tree of `DisplayArea` nodes that group window types under the appropriate feature nodes. This is an automatic process -- the builder determines the minimum set of `DisplayArea` nodes needed to satisfy all feature requirements.

### 23.8.8 DisplayArea Variants

`DisplayArea` has several subclasses for different purposes:

```mermaid
classDiagram
    class DisplayArea~T~ {
        +int mFeatureId
        +String mName
        +boolean mOrganized
    }

    class RootDisplayArea {
        +DisplayAreaPolicy mPolicy
    }

    class DisplayArea_Tokens {
        +addChild(WindowToken)
    }

    class DisplayArea_Dimmable {
        +Dimmer mDimmer
    }

    class TaskDisplayArea {
        +createRootTask()
        +getRootHomeTask()
        +getRootPinnedTask()
    }

    DisplayArea <|-- RootDisplayArea
    DisplayArea <|-- DisplayArea_Tokens
    DisplayArea <|-- DisplayArea_Dimmable
    DisplayArea_Dimmable <|-- TaskDisplayArea
```

- **`DisplayArea.Tokens`**: A leaf `DisplayArea` that holds `WindowToken` instances directly (e.g., for wallpaper, status bar)
- **`DisplayArea.Dimmable`**: A `DisplayArea` that supports dimming its content (used as a base for task areas)
- **`TaskDisplayArea`**: The primary area where application tasks are placed
- **`RootDisplayArea`**: The root of the hierarchy for a display (or a sub-root for display area groups)

### 23.8.9 DisplayAreaOrganizer

Just as `TaskOrganizer` lets Shell control tasks, `DisplayAreaOrganizer` lets Shell control `DisplayArea` nodes. This is used for:

- `RootTaskDisplayAreaOrganizer` -- Controls the root task display area for features like one-handed mode
- `RootDisplayAreaOrganizer` -- Controls the root display area for display-level effects

Organizers receive callbacks when their `DisplayArea` is created or removed, and can apply surface transformations (scale, position, crop) to affect all content within the area.

### 23.8.10 Window Type to DisplayArea Mapping

When a new window is added to the system, `DisplayAreaPolicy.addWindow()` is called to find the correct `DisplayArea` for the window's type. The policy walks the feature tree and places the window in the most specific `DisplayArea.Tokens` node that covers its type.

For example:

- `TYPE_WALLPAPER` (2013) goes to the wallpaper `DisplayArea.Tokens` below the app zone
- `TYPE_STATUS_BAR` (2000) goes to the status bar `DisplayArea.Tokens` above apps but below overlays
- `TYPE_BASE_APPLICATION` (1) goes to the `TaskDisplayArea` via its containing `Task`
- `TYPE_NAVIGATION_BAR` (2019) goes to the navigation bar `DisplayArea.Tokens`
- `TYPE_NOTIFICATION_SHADE` (2040) goes above the navigation bar

This type-based routing is what creates the z-ordering guarantee: system windows above apps, overlays above system windows, and so on.

---

## 23.9 Insets System

### 23.9.1 What Are Insets?

Insets represent regions of the screen that are occupied by system UI (status bar, navigation bar, IME) or display features (cutouts, rounded corners). Windows must account for these regions when laying out their content.

The insets system evolved from legacy `fitSystemWindows()` to the modern `WindowInsets` API with `InsetsController`.

### 23.9.2 InsetsStateController

**Source file:** `frameworks/base/services/core/java/com/android/server/wm/InsetsStateController.java`

`InsetsStateController` is instantiated per-`DisplayContent` and manages the global insets state for that display:

```java
class InsetsStateController {
    private final InsetsState mState = new InsetsState();
    private final DisplayContent mDisplayContent;
    private final SparseArray<InsetsSourceProvider> mProviders = new SparseArray<>();
    private final ArrayMap<InsetsControlTarget, ArrayList<InsetsSourceProvider>>
            mControlTargetProvidersMap = new ArrayMap<>();
}
```

Key concepts:

- **InsetsState**: A snapshot of all insets sources on the display. Each `WindowState` gets a customized `InsetsState` based on its position in the z-order (via `mAboveInsetsState`).

- **InsetsSourceProvider**: Each window that provides insets (status bar, navigation bar, IME) has an `InsetsSourceProvider` registered with the controller.

- **InsetsControlTarget**: Windows that control insets visibility (typically the focused app window). The control target can show/hide system bars with animation.

### 23.9.3 InsetsSource Types

The `WindowInsets.Type` class defines the insets categories:

| Type | Bitmask | Source |
|------|---------|--------|
| `statusBars()` | `1 << 0` | Status bar window |
| `navigationBars()` | `1 << 1` | Navigation bar window |
| `captionBar()` | `1 << 2` | Caption/title bar |
| `ime()` | `1 << 3` | Input method (keyboard) |
| `systemGestures()` | `1 << 4` | System gesture exclusion zones |
| `mandatorySystemGestures()` | `1 << 5` | Mandatory gesture zones |
| `tappableElement()` | `1 << 6` | Tappable system UI elements |
| `displayCutout()` | `1 << 7` | Display cutout regions |

### 23.9.4 Insets Flow: Provider to Consumer

```mermaid
sequenceDiagram
    participant SB as Status Bar Window (InsetsSourceProvider)
    participant ISC as InsetsStateController
    participant FW as Focused App Window (InsetsControlTarget)
    participant IC as InsetsController (client-side)

    Note over SB: Status bar visible,<br/>provides TOP insets

    SB->>ISC: Register InsetsSource(statusBars, frame)
    ISC->>ISC: Update InsetsState
    ISC->>FW: notifyInsetsChanged()
    FW->>IC: WindowInsets dispatched

    Note over IC: App receives insets,<br/>adjusts content area

    IC->>ISC: requestControl(statusBars)
    ISC->>FW: InsetsSourceControl granted

    Note over IC: User swipes to hide status bar

    IC->>ISC: hide(statusBars)
    ISC->>SB: Animate status bar out
```

### 23.9.5 Local Insets Sources

`WindowContainer` supports local insets sources (`mLocalInsetsSources`) that apply only to a subtree of the hierarchy, not the entire display:

```java
// WindowContainer.java
@Nullable
SparseArray<InsetsSource> mLocalInsetsSources = null;
```

These are used for features like caption bars in freeform/desktop mode, where the inset should only apply to windows within a specific task. The `addLocalInsetsFrameProvider()` method supports two frame sources:

- `SOURCE_ARBITRARY_RECTANGLE`: A fixed rectangle defines the insets
- `SOURCE_ATTACHED_CONTAINER_BOUNDS`: The container's own bounds define the insets

Local insets propagate down the hierarchy through `updateAboveInsetsState()`, which merges parent and local insets sources when visiting child containers.

### 23.9.6 Excluded Insets Types

`WindowContainer` also supports insets type exclusion:

```java
protected @InsetsType int mMergedExcludeInsetsTypes = 0;
private @InsetsType int mExcludeInsetsTypes = 0;
```

This allows specific containers to opt out of receiving certain insets types, which is useful for edge-to-edge rendering and custom system UI configurations.

### 23.9.7 IME Insets

The IME (input method editor) is a special insets source (`ID_IME`) with unique handling:

- **IME policy per display**: `DISPLAY_IME_POLICY_LOCAL` means the IME appears on the same display as the focused window; `DISPLAY_IME_POLICY_FALLBACK_DISPLAY` routes IME to the default display
- **Empty control target**: When no window wants IME control, the `mEmptyImeControlTarget` hides the IME:

```java
private final InsetsControlTarget mEmptyImeControlTarget = new InsetsControlTarget() {
    @Override
    public void notifyInsetsControlChanged(int displayId) {
        InsetsSourceControl[] controls = getControlsForDispatch(this);
        for (InsetsSourceControl control : controls) {
            if (control.getType() == WindowInsets.Type.ime()) {
                mDisplayContent.mWmService.mH.post(() ->
                        InputMethodManagerInternal.get().removeImeSurface(displayId));
            }
        }
    }
};
```

### 23.9.8 Insets Animation

The insets system supports animated show/hide of system bars. When the user swipes to hide the navigation bar, or when the IME slides up, the animation is driven by the `InsetsController` on the client side with coordination from `InsetsStateController` on the server side.

The animation flow:

```mermaid
sequenceDiagram
    participant App as InsetsController (client)
    participant ISC as InsetsStateController (server)
    participant SB as System Bar Window
    participant SF as SurfaceFlinger

    App->>ISC: show(navigationBars())
    ISC->>ISC: Grant InsetsSourceControl to App
    ISC-->>App: InsetsSourceControl (leash + initial state)

    loop Animation frames
        App->>SF: setPosition(leash, interpolatedY)
        App->>SF: setAlpha(leash, interpolatedAlpha)
    end

    App->>ISC: insetsAnimationFinished()
    ISC->>SB: Update visible state
```

The `InsetsSourceControl` includes a leash `SurfaceControl` that the client can animate directly, enabling frame-perfect animations without round-trips to the system server.

### 23.9.9 Edge-to-Edge and Insets Consumption

With Android 15's edge-to-edge enforcement, the insets system becomes even more important. Apps that opt into edge-to-edge rendering (or are forced into it) must explicitly handle insets:

```java
// LayoutParams flags
PRIVATE_FLAG_OPT_OUT_EDGE_TO_EDGE  // App explicitly opts out
```

The `FLAG_FORCE_CONSUMING` on `InsetsSource` forces certain insets to be consumed by the window framework even if the app does not handle them, preventing content from rendering behind system bars.

### 23.9.10 Safe Region Bounds

`WindowContainer` supports safe region bounds that constrain where content can appear:

```java
@Nullable
private Rect mSafeRegionBounds;
```

These bounds are used by `AppCompatSafeRegionPolicy` to ensure that content on devices with unusual display shapes (foldables, round displays) remains within the usable area. Safe region bounds propagate down the hierarchy -- a parent's bounds apply to all descendants unless overridden.

---

## 23.10 Shell Features

Shell features are the user-facing window management capabilities built on top of the Shell infrastructure. Each feature is implemented as a module with its own task listener, transition handler, and sometimes dedicated surface management.

### 23.10.1 Picture-in-Picture (PiP)

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/pip/`

PiP allows a video or communication activity to continue in a small floating window. The implementation has phone-specific and TV-specific variants:

- `pip/phone/` -- Phone implementation with drag-to-dismiss, double-tap to resize
- `pip/tv/` -- TV implementation with remote-control navigation

Core components:

- `PipTaskOrganizer` -- Manages the PiP task surface, bounds, and windowing mode changes
- `PipTransition` -- Handles enter/exit PiP transitions via Shell Transitions
- `PipAnimationController` -- Controls animation curves (bounds, alpha, rotation)
- `PipTransitionState` -- State machine tracking the PiP lifecycle

PiP transitions integrate with the broader Shell transition system through custom transition types (`TRANSIT_EXIT_PIP`, `TRANSIT_REMOVE_PIP`, `TRANSIT_PIP_BOUNDS_CHANGE`).

The PiP-to-split-screen flow (`TRANSIT_EXIT_PIP_TO_SPLIT`) demonstrates the cross-feature transition handling: a PiP window expanding into one side of a split-screen layout requires coordinating both the PiP and split-screen modules.

**Cross-reference:** The detailed PiP analysis is in the companion report, Part 2, section 66.

### 23.10.2 Bubbles

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/bubbles/`

Bubbles present notification content as floating, draggable circles that expand into a task-backed UI:

Core components:

- `BubbleController` (30+ supporting classes) -- Central lifecycle management
- `BubbleStackView` -- The floating stack of bubble circles
- `BubbleExpandedView` -- The expanded content pane
- `BubbleData` -- Bubble ordering, overflow, persistence
- `BubbleTransitions` -- Enter/exit/expand/collapse animations
- `BubbleTaskView` -- Task-backed content rendering

Bubbles use `SurfaceControlViewHost` for embedded window rendering, which allows Shell to host a task's content within its own surface hierarchy without a traditional window.

**Cross-reference:** Detailed Bubbles analysis is in Part 2, section 67.

### 23.10.3 Split Screen

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/splitscreen/`

Split screen divides the display into two (or more) stages:

Core components:

- `SplitScreenController` -- Public API surface, IPC interface
- `StageCoordinator` -- Orchestrates layout, bounds, divider position
- `StageCoordinator2.kt` -- Next-generation Kotlin coordinator
- `StageTaskListener` -- Per-stage task lifecycle listener
- `SplitScreenTransitions` -- Enter/exit/dismiss animations
- `SplitLayout` -- Divider geometry, snap points, parallax

Split screen supports multiple entry mechanisms:

- Drag from recents
- Launch-adjacent intent flag
- Long-press in recents for split-screen shortcut
- Desktop mode drag to screen edge

**Cross-reference:** Detailed split screen analysis is in Part 2, section 68.

### 23.10.4 Desktop Windowing

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/`

Desktop windowing is the most complex Shell feature, providing a full desktop experience with:

- **Freeform windows** with title bars, resize handles, minimize/maximize/close buttons
- **Task limiting** (`DesktopTasksLimiter`) to manage resource usage
- **Window drag** (`WindowDragTransitionHandler`) for move/resize operations
- **Desktop wallpaper** (`DesktopWallpaperActivity`) as a background surface
- **Multi-desk support** (`multidesks/`, with `DesksController` and `DesksOrganizer`) for virtual desktop switching
- **Cross-display moves** (`DesktopModeMoveToDisplayTransitionHandler`, `DisplayDisconnectTransitionHandler`) for multi-display desktop
- **Immersive mode** (`DesktopImmersiveController`) for fullscreen apps in desktop
- **IME handling** (`DesktopImeHandler`) for keyboard layout in freeform windows
- **Minimization** (`minimize/`) for task bar integration

The desktop mode directory alone contains 50+ files, reflecting the significant engineering investment in bringing desktop-class windowing to Android.

**Multiple desks.** A single display can host more than one *desk* (virtual
desktop), each with its own set of open windows, in the same way a Linux desktop
offers several workspaces. The `multidesks/` package implements this on top of
the desktop-windowing stack. `DesksController`
(`.../desktopmode/multidesks/DesksController.kt`) owns the create/activate/
deactivate/remove logic and drives a `DesksOrganizer` (the `RootTaskDesksOrganizer`
implementation) that gives each desk its own root task container under the
display's `TaskDisplayArea`; activating a desk reorders its container to the
front and a `DeskSwitchTransitionHandler` animates the lateral move between two
desks on the same display. The per-desk state -- `activeTasks`, `visibleTasks`,
`minimizedTasks`, and the `leftTiledTaskId`/`rightTiledTaskId` snap slots -- is
held in the `Desk` data model (`.../desktopmode/data/Desk.kt`) inside the
per-display `DesktopRepository`, which `DesktopUserRepositories` instantiates per
user. So multiple desks reuse the existing per-display task hierarchy and
transition machinery rather than introducing a parallel one: a desk is a root
task the organizer shows or hides, and switching desks is an ordinary Shell
transition.

A few desktop sub-features round out the surface presentation.
`DesktopWallpaperActivity` (`.../desktopmode/DesktopWallpaperActivity.kt`) is a
transparent activity that paints the wallpaper behind the freeform windows, gated
by `enable_desktop_windowing_wallpaper_activity`. `DesktopImmersiveController`
(`.../desktopmode/DesktopImmersiveController.kt`) moves a freeform task in and out
of a full-immersive state where the task fills the display and the status bar is
transient, via `moveTaskToImmersive()`. `DesktopHomeScreenPeekController`
(`.../desktopmode/homescreenpeeking/DesktopHomeScreenPeekController.kt`) shifts
the desktop windows toward a screen edge to peek at the home screen behind them,
gated by `enable_home_screen_peeking`. First-run onboarding for the desktop
gestures lives in `education/`: `AppHandleEducationController` introduces the
app-handle drag that pulls an app into a freeform window
(`enable_desktop_windowing_app_handle_education`), and
`AppToWebEducationController` introduces the app-to-web transition
(`enable_desktop_windowing_app_to_web_education`,
`enable_enhanced_app_to_web_transition`).

**Cross-reference:** Chapter 22 (Activity and Window Management) covers the *WM-core* side of desktop windowing -- how `Task` windowing modes, the desktop task lifecycle, and `DesktopExperienceFlags` gating drive policy. This chapter covers the *Shell presentation* side: the surfaces, transition handlers, and caption decorations that animate desktop windows. Detailed desktop mode analysis is also in the companion report, Part 2, section 69.

### 23.10.5 Predictive Back

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/back/`

Predictive back implements the Android 14+ back gesture system where swiping back shows a preview of the destination before committing:

Core components:

- `BackAnimationController` -- Gesture progress tracking, animation selection
- `CrossTaskBackAnimation` -- Animation between different tasks
- `CrossActivityBackAnimation.kt` -- Animation between activities in same task
- `DefaultCrossActivityBackAnimation.kt` -- Default cross-activity animation
- `CustomCrossActivityBackAnimation.kt` -- Custom animations (shared element, etc.)
- `ShellBackAnimationRegistry` -- Registration of back animation handlers

Predictive back uses `ANIMATION_TYPE_PREDICT_BACK` in the `SurfaceAnimator` system, allowing it to coexist with other animation types.

**Cross-reference:** Detailed predictive back analysis is in Part 2, section 70.

### 23.10.6 Additional Shell Features

| Feature | Directory | Purpose |
|---------|-----------|---------|
| Window Decorations | `windowdecor/` | Caption bars, resize handles for freeform/desktop windows |
| One-Handed Mode | `onehanded/` | Shifts display content down for one-hand use |
| Unfold Animation | `unfold/` | Foldable device unfold transition |
| App-to-Web | `apptoweb/` | Cross-context transitions between app and web content |
| App Zoom Out | `appzoomout/` | Display-level zoom out effect |
| Activity Embedding | `activityembedding/` | Embedded activities within tasks |
| Compat UI | `compatui/` | Letterboxing, size compatibility UI |
| Starting Surface | `startingsurface/` | Splash screen management |
| Fullscreen | `fullscreen/` | Default fullscreen task handling |
| Keyguard | `keyguard/` | Lock screen transition integration |
| Recents | `recents/` | Recent apps integration |
| Crash Handling | `crashhandling/` | App crash UX within windowed modes |
| Drag and Drop | `draganddrop/` | Cross-window drag and drop |
| Pinned Layer | `pinnedlayer/` | Pinned surface management |

### 23.10.7 Feature Module Pattern

All Shell features follow a consistent architectural pattern:

```mermaid
graph TB
    subgraph "Feature Module Pattern"
        IFACE["Feature Interface<br/>(e.g., Pip.java, SplitScreen.java)<br/>Public API for external callers"]
        CTRL["Feature Controller<br/>(e.g., PipController, SplitScreenController)<br/>External API implementation"]
        TASK["Feature TaskListener<br/>(e.g., PipTaskOrganizer, StageTaskListener)<br/>Task lifecycle management"]
        TRANS["Feature TransitionHandler<br/>(e.g., PipTransition, SplitScreenTransitions)<br/>Animation logic"]
        STATE["Feature State<br/>(e.g., PipTransitionState, SplitState)<br/>State tracking"]
    end

    IFACE --> CTRL
    CTRL --> TASK
    CTRL --> TRANS
    CTRL --> STATE
    TASK --> STATE
    TRANS --> STATE

    subgraph "Shell Infrastructure"
        STO["ShellTaskOrganizer"]
        TR["Transitions"]
        SC["ShellController"]
    end

    TASK -->|"registerTaskListener"| STO
    TRANS -->|"registerHandler"| TR
    CTRL -->|"registerFeature"| SC
```

Each feature module:

1. **Registers** a task listener with `ShellTaskOrganizer` for its windowing mode
2. **Registers** a transition handler with `Transitions` for its custom transition types
3. **Registers** itself with `ShellController` for lifecycle management
4. **Exposes** a public interface (AIDL or Java) for external callers (SystemUI, Launcher)

### 23.10.8 MixedTransitionHandler: Cross-Feature Coordination

The `MixedTransitionHandler` handles transitions that span multiple features simultaneously:

**Source file:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/transition/MixedTransitionHandler.java`

Mixed transitions arise in several scenarios:

| Scenario | Features Involved |
|----------|-------------------|
| Entering split while PiP is active | Split + PiP |
| PiP entering while keyguard shows | PiP + Keyguard |
| Desktop task moving while split is active | Desktop + Split |
| Recents gesture while PiP is visible | Recents + PiP |

The `MixedTransitionHandler` detects these scenarios by examining the `TransitionInfo` changes and delegates sub-animations to the appropriate feature handlers while coordinating their timing.

`DefaultMixedTransition` and `RecentsMixedTransition` are specific implementations for common mixed scenarios:

```
MixedTransitionHandler
├── DefaultMixedTransition    — General cross-feature handling
└── RecentsMixedTransition    — Recents + other feature handling
```

### 23.10.9 Window Decorations

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/windowdecor/`

Window decorations provide title bars (caption bars) for freeform and desktop-mode windows. The implementation uses `SurfaceControlViewHost` to render the decoration views within Shell's surface hierarchy, above the task's content but below system overlays.

Key capabilities:

- **Drag-to-move**: Title bar serves as a drag handle for window positioning
- **Resize handles**: Edge and corner handles for window resizing
- **Window controls**: Minimize, maximize/restore, close buttons
- **Title display**: Shows the activity label
- **Theming**: Adapts to light/dark mode and accent colors
- **View host pooling**: Reuses `SurfaceControlViewHost` instances for efficiency

The caption bar system has evolved from a legacy `DecorView`-based approach (where the app process rendered its own title bar) to a Shell-based approach (where Shell renders the title bar externally). The Shell approach provides consistent styling, eliminates app-side rendering overhead, and enables system-level drag/resize handling.

Resizing also covers *snapping*. Dragging a freeform window to a screen edge, or
toggling maximize, snaps it to half the display through `SnapController`
(`frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/SnapController.kt`),
whose `snapToHalfScreen()` takes a `DesktopTasksController.SnapPosition` (left or
right) and is wired into the window-decoration drag positioners. Snapping works
across monitors when `enable_cross_display_snap_support` is set, and
`enable_freeform_box_shadows_v2` controls the drop shadow drawn around freeform
windows.

### 23.10.10 Shell Initialization and Lifecycle

Shell features are initialized through `ShellInit`, which provides a deterministic initialization order:

```mermaid
sequenceDiagram
    participant SI as ShellInit
    participant SC as ShellController
    participant STO as ShellTaskOrganizer
    participant TR as Transitions
    participant PIP as PipController
    participant SPLIT as SplitScreenController
    participant DESK as DesktopTasksController
    participant BACK as BackAnimationController

    SI->>SC: init()
    SI->>STO: init()
    SI->>TR: init()
    SI->>PIP: init()
    SI->>SPLIT: init()
    SI->>DESK: init()
    SI->>BACK: init()

    Note over STO: Register with WM Core<br/>TaskOrganizer
    Note over TR: Register as ITransitionPlayer<br/>with WM Core
    Note over PIP: Register PIP listener<br/>with ShellTaskOrganizer
    Note over SPLIT: Register split listener<br/>with ShellTaskOrganizer
```

The initialization order matters because features depend on infrastructure components. `ShellTaskOrganizer` must register with WM Core before feature modules can register their listeners with it. `Transitions` must register as the transition player before feature modules can register their handlers.

### 23.10.11 Shell Error Handling

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/crashhandling/`

`ShellCrashHandler` manages what happens when a Shell component encounters an unrecoverable error. Since Shell runs in the system server process, an unhandled exception could crash the entire system. The crash handler:

1. Catches exceptions from Shell components
2. Logs the error with full stack trace
3. Attempts graceful degradation (e.g., exiting split screen, exiting PiP)
4. Reports to telemetry for analysis

### 23.10.12 Performance Monitoring

**Directory:** `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/performance/`

Shell integrates with Android's `SystemPerformanceHinter` to provide performance hints during transitions:

- Transition start triggers a performance boost hint
- Heavy animations (split enter, desktop window drag) request sustained performance
- Animation completion releases the performance boost

The `InteractionJankMonitor` integration tracks frame drops during Shell-driven animations, enabling jank detection and reporting for transitions, PiP resize, split divider drag, and other interactive operations.

---

## 23.11 Detailed Reference

### 23.11.1 The Three-Part Companion Report

This chapter provides the architectural foundation for the window system. For a deep dive into every subsystem, consult the companion three-part report located in the book's supplementary materials:

| Part | Sections | Coverage |
|------|----------|----------|
| **Part 1: Foundations** | Sections 1-45 | Architecture overview, Android vs Linux graphics stack, Activity/Window/Task relationship, WM Core and Shell, transitions, animations, display system, multi-window, multi-display, rendering pipeline, input system |
| **Part 2: Features** | Sections 46-75 | SystemUI/Launcher integration, testing, caption bars, drag and drop, buffer management, virtual displays, companion devices, display refresh, rotation, foldables, keyguard, starting windows, app compatibility, wallpaper, color management, window types, accessibility, IME, PiP, Bubbles, split screen, desktop mode, predictive back, client-side architecture, configuration, multi-user, task snapshots, security |
| **Part 3: Platform** | Sections 76-100 | System UI windows, power/performance, task management, accessibility features, foldable shell, debugging, content protection, architectural evolution, display cutout, SurfaceFlinger FrontEnd, system keys, boot animation, atomic operations, display mirroring, automotive, TaskFragment, dreams, synchronization, TV WM, Wear OS WM, window decoration |

### 23.11.2 Quick Section Finder

For common topics, use this cross-reference to find the relevant section(s) in the companion report:

| Topic | Report Section(s) |
|-------|-------------------|
| How activities map to windows | Part 1, section 5 |
| Task and TaskFragment hierarchy | Part 1, sections 6, Part 3 section 95 |
| WM Core internals | Part 1, section 7 |
| WM Shell architecture | Part 1, section 8 |
| Shell DI and threading | Part 1, sections 10-11 |
| Transition animation framework | Part 1, sections 15-19 |
| Surface leash mechanism | Part 1, section 16 |
| DisplayArea hierarchy | Part 1, section 22 |
| Insets system | Part 1, section 23 |
| Multi-window modes | Part 1, sections 26-31 |
| Multi-display | Part 1, sections 32-35 |
| InputFlinger integration | Part 1, section 44 |
| PiP implementation | Part 2, section 66 |
| Bubbles implementation | Part 2, section 67 |
| Split screen implementation | Part 2, section 68 |
| Desktop windowing | Part 2, section 69 |
| Predictive back | Part 2, section 70 |
| ViewRootImpl client side | Part 2, section 71 |
| Buffer management | Part 2, sections 51-52 |
| HWUI and rendering | Part 1, section 37 |
| SurfaceFlinger composition | Part 3, section 89 |
| Window decoration (DecorView) | Part 3, section 100 |
| Debugging and tracing | Part 3, section 84 |

### 23.11.3 Key Source Files Reference

The following table lists the most important source files for each section of this chapter, with line counts to indicate complexity:

Line counts are approximate as of the Android 17 (`android17-release`) tree.

| File | Lines | Chapter Section |
|------|-------|-----------------|
| `WindowManagerService.java` | ~11,600 | 23.1 (Architecture) |
| `WindowContainer.java` | ~3,800 | 23.1 (Hierarchy) |
| `WindowState.java` | ~6,400 | 23.1 (Window state) |
| `DisplayContent.java` | ~7,700 | 23.1, 23.5 (Display) |
| `RootWindowContainer.java` | ~3,950 | 23.1 (Hierarchy root) |
| `Task.java` | ~7,560 | 23.1, 23.4 (Tasks) |
| `ActivityRecord.java` | ~9,900 | 23.1 (Activities) |
| `TaskFragment.java` | ~3,550 | 23.1 (Task fragments) |
| `DisplayArea.java` | ~880 | 23.8 (Z-order) |
| `DisplayAreaPolicy.java` | -- | 23.8 (Z-order policy) |
| `TransitionController.java` | ~2,240 | 23.3 (Core transitions) |
| `Transition.java` | ~4,970 | 23.3 (Transition state) |
| `Transitions.java` (Shell) | -- | 23.3 (Shell animation) |
| `SurfaceAnimator.java` | ~640 | 23.7 (Leash mechanism) |
| `InsetsStateController.java` | ~580 | 23.9 (Insets) |
| `InputMonitor.java` | -- | 23.6 (Input) |
| `StageCoordinator.java` | -- | 23.4 (Split screen) |
| `PipTaskOrganizer.java` | -- | 23.4 (PiP) |
| `DesktopTasksController.kt` | -- | 23.4 (Desktop) |
| `BackAnimationController.java` | -- | 23.10 (Predictive back) |
| `WMShellModule.java` | -- | 23.2 (DI) |
| `WMShellConcurrencyModule.java` | -- | 23.2 (Threading) |

### 23.11.4 Debugging the Window System

The window system provides extensive debugging infrastructure:

**dumpsys commands:**

```bash
# Full WMS state dump
adb shell dumpsys window

# Windows only
adb shell dumpsys window windows

# Display state
adb shell dumpsys window displays

# Transitions
adb shell dumpsys window transitions

# Focused window
adb shell dumpsys window focus

# Window containers hierarchy
adb shell dumpsys window containers

# Display areas
adb shell dumpsys window display-areas

# Input dispatch state
adb shell dumpsys input
```

**Perfetto tracing:**

The window system integrates with Perfetto for production-quality tracing. Key trace categories:

- `TRACE_TAG_WINDOW_MANAGER` -- All WM operations
- Window state changes are logged as Perfetto trace events
- Transition lifecycle is traced from creation through finish
- `TransitionTracer` provides specialized transition tracing

**ProtoLog:**

WM Core uses ProtoLog for structured logging with per-group enable/disable:

```java
// Log groups (can be enabled/disabled at runtime)
WM_DEBUG_ADD_REMOVE         // Window add/remove operations
WM_DEBUG_FOCUS              // Focus changes (verbose)
WM_DEBUG_FOCUS_LIGHT        // Focus changes (brief)
WM_DEBUG_ANIM               // Animation events
WM_DEBUG_ORIENTATION        // Orientation changes
WM_DEBUG_WINDOW_TRANSITIONS_MIN // Transition events (minimal)
WM_DEBUG_SYNC_ENGINE        // BLAST sync engine events
WM_DEBUG_BOOT               // Boot sequence
WM_DEBUG_SCREEN_ON          // Screen on/off
WM_DEBUG_STARTING_WINDOW    // Starting window lifecycle
WM_DEBUG_WINDOW_MOVEMENT    // Window position changes
WM_ERROR                    // Error conditions
WM_SHOW_TRANSACTIONS        // Surface transactions
WM_SHOW_SURFACE_ALLOC       // Surface allocation/deallocation
```

Shell has its own ProtoLog groups (e.g., `WM_SHELL_TRANSITIONS`, `WM_SHELL_SPLIT_SCREEN`) for feature-specific logging.

**Window traces:**

`WindowTracing` captures periodic snapshots of the entire window hierarchy as Protocol Buffer messages, which can be analyzed with the Winscope tool for debugging layout, visibility, and z-order issues.

### 23.11.5 Architecture Cheat Sheet

For quick reference, the core architectural patterns:

1. **WindowContainer tree** -- All window entities form a single tree rooted at `RootWindowContainer`. Each node has a 1:1 `SurfaceControl`.

2. **Organizer pattern** -- `TaskOrganizer`, `DisplayAreaOrganizer`, `TaskFragmentOrganizer` allow Shell to subscribe to and control subsets of the hierarchy without modifying Core.

3. **Shell transitions** -- WM Core collects participating containers into a `Transition`, waits for readiness, then hands a `TransitionInfo` to Shell for animation. Shell returns control via `finishTransition()`.

4. **Leash animation** -- To animate a surface subtree, a new "leash" surface is interposed between the container and its parent. The animation target is the leash; children move with it.

5. **Insets contract** -- Windows that provide insets register `InsetsSourceProvider`s. Windows that consume insets receive `InsetsState` snapshots. The focused window can control insets visibility via `InsetsSourceControl`.

6. **Per-display isolation** -- Each `DisplayContent` has its own `InsetsStateController`, `InputMonitor`, focus tracking, and `DisplayArea` hierarchy. Cross-display operations require explicit reparenting.

7. **Dagger DI for variant customization** -- Phone, TV, and Auto swap Dagger modules to provide variant-specific Shell feature implementations (e.g., TV PiP vs Phone PiP).

---

## 23.12 Android 17 Window System Changes

Android 17 does not restructure the window system, but it does land focused changes on the parts this chapter owns: insets delivery, connected-display presentation, and caption-bar handling. The desktop *windowing-mode policy and lifecycle* live in WM core and are covered in Chapter 22; the changes below are the window, surface, insets, and display-side pieces. Each flag here is a real entry in the Android 17 (`android17-release`) tree, so a reader can grep the same name in source.

### 23.12.1 Insets Delivery and Rotation

Two `windowing_frontend` flags refine how insets reach clients.

**Source file:** `frameworks/base/core/java/android/window/flags/windowing_frontend.aconfig`

- `send_new_insets_state_with_rotation` -- *"Send the new InsetsState to the shell when the display rotates."* Before this, the insets snapshot and the rotation could be delivered out of step, so a client could briefly lay out against pre-rotation insets. The display-update path now bundles the fresh `InsetsState` with the rotation event. The flag is read in `DisplayUpdater.java`, `DeferredDisplayUpdater.java`, and `DisplayRotation.java` (all under `frameworks/base/services/core/java/com/android/server/wm/`) via `com.android.window.flags.Flags.sendNewInsetsStateWithRotation()`.

- `synced_insets_animation` -- *"Synchronize the applied insets to a view with the ongoing system insets animation."* This is a client-side change consumed in `frameworks/base/core/java/android/view/InsetsController.java` and `frameworks/base/core/java/android/view/ViewRootImpl.java`. It keeps the insets a view sees in step with the in-flight system-bar/IME animation, so content does not jump a frame ahead of (or behind) the bar it is reacting to. This refines the insets contract described in section 23.9 rather than replacing it: the server still grants an `InsetsSourceControl` with a leash, and the client still animates it; the flag just tightens the timing of when the *applied* insets value updates.

Insets delivery on rotation (Android 17):

```mermaid
sequenceDiagram
    participant DR as DisplayRotation
    participant DU as DisplayUpdater
    participant ISC as InsetsStateController
    participant Client as ViewRootImpl / InsetsController

    DR->>DU: rotation computed
    Note over DU: sendNewInsetsStateWithRotation()<br/>bundles fresh InsetsState
    DU->>ISC: snapshot InsetsState for new rotation
    ISC->>Client: rotation + matching InsetsState together
    Note over Client: syncedInsetsAnimation()<br/>keeps applied insets in step<br/>with ongoing bar/IME animation
```

### 23.12.2 Connected-Display Presentation

The connected-display work (external monitors, large screens) adds display-side gates in the `lse_desktop_experience` namespace.

**Source file:** `frameworks/base/core/java/android/window/flags/lse_desktop_experience.aconfig`

- `mask_presentation_flags_on_internal_displays` -- *"Mask Display.FLAG_PRESENTATION for certain apps on internal displays."* Some apps treat any `FLAG_PRESENTATION` display as a secondary external screen; on a connected-display device the internal panel should not look like a presentation target to those apps, so the flag masks the flag for them.
- `enable_connected_displays_wallpaper_presentations` -- extends wallpaper presentation to connected external displays.
- `disable_display_force_freeform_on_pc` -- *"Prevents a display from being forced to freeform solely due to it being on PC."* A display attached to a PC form factor is no longer unconditionally pushed into freeform windowing; the windowing mode is decided by policy instead.
- `enable_presentation_stops_top_task_bugfix` -- corrects top-task handling when a presentation is shown on a display.

The display content-mode machinery itself is gated by `DesktopExperienceFlags.ENABLE_DISPLAY_CONTENT_MODE_MANAGEMENT`, read in `DisplayContent.java` (e.g. around the content-mode update paths). `DesktopExperienceFlags` (`frameworks/base/core/java/android/window/DesktopExperienceFlags.java`) is the Android 17 gating mechanism that wraps these window flags with a developer-options override, so the whole connected-display feature can be toggled coherently for testing.

On the Shell side, two transition handlers in `frameworks/base/libs/WindowManager/Shell/src/com/android/wm/shell/desktopmode/` own the surface choreography when displays come and go:

- `DesktopModeMoveToDisplayTransitionHandler.kt` -- animates moving a desk task to another display.
- `DisplayDisconnectTransitionHandler.kt` -- *"animate the transition from disconnecting a display,"* migrating its content off the removed display (its own source TODO notes it may move out of the desktop package as it generalizes).

These complement, rather than replace, the per-`DisplayContent` reparenting model from section 23.5: WM core still reparents `Task` containers across `DisplayContent` instances, and these handlers provide the Shell-side animation for that reparent.

### 23.12.3 Caption-Bar Insets Refactor

Caption bars (the title bars on freeform/desktop windows from section 23.10.9) gained finer insets control in Android 17.

- `FLAG_FORCE_CONSUMING_OPAQUE_CAPTION_BAR` (`frameworks/base/core/java/android/view/InsetsSource.java`) is a caption-specific sibling of `FLAG_FORCE_CONSUMING` (section 23.9.9). When set, the `captionBar()` insets are consumed *even when the caption bar is requested visible* -- unless the window opts into `APPEARANCE_TRANSPARENT_CAPTION_BAR_BACKGROUND`. This lets the system keep app content out from under an opaque caption while still allowing apps that draw their own transparent caption background to take the space.
- `refactor_caption_sandboxing_to_core` (`lse_desktop_experience`) -- *"Refactor sandboxing of caption insets from app bounds from shell to core."* The logic that excludes caption insets from an app's reported bounds is moving from Shell into WM core, consolidating where the app-bounds sandboxing decision is made.
- `exclude_caption_insets_opt_out_api` (exported) -- *"Allow app developers to opt out from OVERRIDE_EXCLUDE_CAPTION_INSETS_FROM_APP_BOUNDS,"* giving apps a public API to opt out of the caption-insets exclusion behavior.

Together these tighten the section 23.9 insets model for the desktop/caption case: caption insets become a first-class, core-owned insets source with an explicit consume policy and an app opt-out, rather than a Shell-only adjustment to app bounds.

### 23.12.4 Flexible Split

The two-pane split from section 23.4.2 is generalizing toward flexible layouts in Android 17, gated by Shell flags in `frameworks/base/libs/WindowManager/Shell/aconfig/multitasking.aconfig`:

- `enable_flexible_split` -- read across `StageCoordinator.java` and `DesktopTasksController.kt` as `com.android.wm.shell.Flags.enableFlexibleSplit()`.
- `enable_flexible_two_app_split` -- read in `SplitStatusBarHider.kt` and related split components as `enableFlexibleTwoAppSplit()`, covering the two-app flexible split layout (including 10:90 / 90:10 ratios) and the matching status-bar handling.

The new `LayoutEngine.kt` (`.../splitscreen/LayoutEngine.kt`) computes flexible-split bounds from a node tree (`calculateFlexibleSplit()`), which is the layout substrate for moving beyond a single fixed divider. This is an evolution of the `StageCoordinator` / `SplitLayout` model in section 23.4.2, not a replacement: the stage and listener structure is unchanged.

### 23.12.5 SurfaceControlViewHost and Surface Mirroring

Android 17 lands a cluster of changes on the cross-process view-embedding path -- `SurfaceControlViewHost` (SCVH) and its engine `WindowlessWindowManager` -- plus a new public surface-mirroring API. SCVH is the mechanism that lets one process host a `View` hierarchy inside another process's `SurfaceControl` tree (used by Bubbles in 23.10.2 and window decorations in 23.10.9); these changes refine it rather than restructure it.

**A new public mirror API.** `AttachedSurfaceControl.createMirror()` (`@FlaggedApi(mirror_surface_api)`, `frameworks/base/core/java/android/view/AttachedSurfaceControl.java`; the working implementation is `ViewRootImpl.createMirror()`, line 13104) returns a new `SurfaceControl` that parents a *mirror* of the window's root surface hierarchy. Transforms applied to the returned control affect only the copy, not the original, so an app can show a live duplicate of its own content on another surface without re-rendering it. The flag description is explicit: "allows apps to get [a] mirrored surface control of [their] own window." The caller owns the returned control and must `release()` it.

createMirror() parents an independent copy of the window's surface tree:

```mermaid
graph TD
    subgraph REAL["Window root hierarchy"]
        A["A = root SurfaceControl"] --> B["B = child"]
    end
    subgraph MIR["createMirror() result"]
        SC["SC = returned parent"] --> Ap["A' = mirror of A"]
        Ap --> Bp["B' = mirror of B"]
    end
    A -. "mirrored" .-> Ap
    B -. "mirrored" .-> Bp
```

**Identifiable embedded surfaces.** `SCVH.setView` now names the backing `SurfaceControl` with the hosting package -- `setName("SurfaceControlViewHost[" + context.getPackageName() + "]")` -- and the SCVH `Builder` gained `setTitle()` / `getTitle()` (`@FlaggedApi(scvh_set_focusable_api)`), whose title is threaded into the window `LayoutParams` (`wmLayoutParams.setTitle(mTitle)`) and the windowless input-handle name. Both make embedded surfaces identifiable in `dumpsys SurfaceFlinger` and Winscope, where every SCVH surface previously shared the generic name "SurfaceControlViewHost". A new `@hide getViewRoot()` exposes the wrapped `ViewRootImpl`.

**Focus and lifetime fixes.** The flag gating SCVH's focus-control API was renamed `scvh_set_focusable` -> `scvh_set_focusable_api`, and a companion bugfix flag `scvh_surface_control_lifetime_fix` ("Fix lifetime issue with SurfaceControl's created by SCVH") closes a real lifetime bug in SCVH-created surfaces (both in `frameworks/base/core/java/android/window/flags/window_surfaces.aconfig`).

**Windowless input plumbing refactor.** `WindowlessWindowManager` now passes a single `WindowInputChannelParams` struct (`frameworks/base/core/java/android/view/WindowInputChannelParams.aidl`) to `grantInputChannel()` / `updateInputChannel()` instead of long positional argument lists, and it calls `dispatchStateToClients()` on state changes so embedded hosts learn about host-token and configuration updates (it forwards `onConfigurationChanged` and the host `InputTransferToken` through `onDispatchAttachedToWindow`). The dead `addToDisplayWithoutInputChannel()` override was removed.

These are distinct from out-of-process rendering (Chapter 13, section 13.41). SCVH embeds a *live View hierarchy* from another process by sharing SurfaceControls and input channels, and that hierarchy still renders in the embedded process; OOPR instead ships a *recorded command buffer* for SurfaceFlinger to replay. Both cross the process boundary through SurfaceControl transactions, but they solve different problems.

---

## Try It

Use a device or emulator running Android 17 (`android17-release`) to observe the structures this chapter describes. The window system exposes most of its state through `dumpsys window`.

1. **Walk the WindowContainer tree.** Run `adb shell dumpsys window containers` and trace the hierarchy from `RootWindowContainer` down through `DisplayContent`, the `DisplayArea` nodes, `TaskDisplayArea`, `Task`, `ActivityRecord`, and `WindowState` (section 23.1.4). Confirm system windows (status bar, nav bar, IME) sit in their own `DisplayArea.Tokens` nodes separate from the app `TaskDisplayArea`.

2. **Inspect per-display insets.** With an app open, run `adb shell dumpsys window displays` and find the `InsetsState` / `InsetsSourceProvider` block (section 23.9). Show or hide the IME and re-dump to see the `ime()` source appear and disappear, and the focused window's `InsetsControlTarget` change.

3. **Watch a transition.** Run `adb shell dumpsys window transitions`, then launch and close an app while re-dumping. Observe a `Transition` move through collecting/ready/playing, and note the track assignment (section 23.3.9). Capturing a Winscope trace during the launch lets you replay the leash animation (section 23.7.2) frame by frame.

4. **Exercise the Android 17 paths.** If the device supports connected displays or desktop windowing, enable the desktop-experience developer toggle (backed by `DesktopExperienceFlags`, section 23.12.2) and attach an external display. Move a window between displays and watch `dumpsys window displays` show the `Task` reparent to the second `DisplayContent`. Rotate the device with an app that reacts to insets to see the bundled rotation + `InsetsState` delivery (section 23.12.1).

5. **Map a window type to its layer.** Pick a window from `dumpsys window windows`, note its type and the `DisplayArea` it landed in, and reconcile that against the type-to-`DisplayArea` routing in sections 23.8.5 and 23.8.10.

## Summary

### Architecture Recap

The Android window system is a three-tier architecture:

- **WM Core** (system server) manages the `WindowContainer` hierarchy, enforces policy, coordinates transitions, and synchronizes with SurfaceFlinger
- **WM Shell** (Shell library) manages surface presentation, drives transition animations, and implements feature UIs (PiP, split screen, bubbles, desktop mode)
- **SurfaceFlinger** (native compositor) composites the surface tree onto physical and virtual displays

### Key Design Patterns

1. **WindowContainer hierarchy** -- All window entities form a single tree rooted at `RootWindowContainer`. Each node maintains a 1:1 `SurfaceControl` in SurfaceFlinger's layer tree. The tree is ordered bottom-to-top in the `mChildren` list.

2. **Organizer pattern** -- `TaskOrganizer`, `DisplayAreaOrganizer`, and `TaskFragmentOrganizer` allow Shell to subscribe to and control subsets of the hierarchy via callbacks, without modifying Core policy code.

3. **Shell transitions** -- WM Core collects participating containers into a `Transition`, waits for readiness via `BLASTSyncEngine`, then hands a `TransitionInfo` with surface leashes to Shell for animation. Shell returns control via `finishTransition()`. Multiple tracks enable parallel animations.

4. **Leash animation** -- To animate a surface subtree, a new "leash" `EffectLayer` is interposed between the container and its parent. The animation transforms the leash; children move with it. After animation, children are reparented back.

5. **Insets contract** -- Windows providing system UI register `InsetsSourceProvider`s. Consuming windows receive `InsetsState` snapshots. The focused window controls insets visibility via `InsetsSourceControl` with direct leash animation.

6. **Per-display isolation** -- Each `DisplayContent` has its own `InsetsStateController`, `InputMonitor`, focus tracking, `DisplayAreaPolicy`, and `DisplayArea` hierarchy. Cross-display operations require explicit reparenting with configuration updates.

7. **Dagger DI for variant customization** -- Phone, TV, and Auto swap Dagger modules (`WMShellModule`, `TvWMShellModule`) to provide variant-specific Shell feature implementations while sharing `WMShellBaseModule` infrastructure.

8. **Transaction atomicity** -- All surface changes within a placement cycle accumulate in a single `SurfaceControl.Transaction` and apply atomically, ensuring users never see intermediate states.

### Scale of the System

The window system is one of the largest subsystems in AOSP:

| Component | Approximate Lines | Files |
|-----------|-------------------|-------|
| WM Core (`server/wm/`) | 200,000+ | 250+ |
| WM Shell (`wm/shell/`) | 150,000+ | 400+ |
| Window API (`view/`) | 50,000+ | 50+ |
| Total | 400,000+ | 700+ |

The five largest individual source files in the Android 17 tree -- `WindowManagerService.java` (~11,600 lines), `ActivityRecord.java` (~9,900 lines), `DisplayContent.java` (~7,700 lines), `Task.java` (~7,560 lines), and `WindowState.java` (~6,400 lines) -- together exceed 43,000 lines of Java code, reflecting the deep complexity of window management.

### Evolution Direction

The window system is evolving in several clear directions:

1. **Desktop-first**: Over 50 files in the `desktopmode/` directory, plus feature flags for desktop windowing, multi-desk support, and display focus management, signal a strategic push toward desktop-class computing.

2. **Kotlin adoption**: New Shell components (like `StageCoordinator2.kt`, `DesktopTasksController.kt`, `WindowDragTransitionHandler.kt`) are written in Kotlin, while existing Java components are maintained.

3. **Parallel transitions**: The track-based parallel transition system continues to evolve with flags like `ENABLE_PARALLEL_CD_TRANSITIONS_DURING_RECENTS` for more concurrent animation support.

4. **Multi-display maturity**: Android 17 flags like `enable_connected_displays_wallpaper_presentations` and `mask_presentation_flags_on_internal_displays`, the `DesktopExperienceFlags.ENABLE_DISPLAY_CONTENT_MODE_MANAGEMENT` gate, and the cross-display desk handlers (`DesktopModeMoveToDisplayTransitionHandler`, `DisplayDisconnectTransitionHandler`) indicate deepening multi-display support beyond mirroring toward true multi-display computing (see section 23.12).

5. **Flexible split**: The `enableFlexibleSplit` and `enableFlexibleTwoAppSplit` flags suggest movement toward more dynamic multi-window layouts beyond the traditional two-pane split.

For the 100-section deep dive into every subsystem, implementation detail, and edge case, see the companion three-part report (Part 1: sections 1-45, Part 2: sections 46-75, Part 3: sections 76-100).
