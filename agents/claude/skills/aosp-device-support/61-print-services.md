# Chapter 61: Print Services

Android's printing framework provides a complete system for discovering printers,
rendering documents, spooling print jobs, and delivering them to physical or
virtual printers. The framework uses a layered architecture: a system service
(`PrintManagerService`) manages per-user state and coordinates between
applications, a print spooler process manages the print queue, and pluggable
print services handle communication with specific printers or protocols.

This chapter examines the printing framework from the public API through the
system service internals, covering the print job lifecycle, document rendering,
printer discovery, and the spooler architecture.

---

## 61.1 Architecture Overview

The printing framework is organized into four major layers:

```mermaid
graph TB
    subgraph "Application Layer"
        APP["Application"]
        PM["PrintManager<br/>(client API)"]
        PDA["PrintDocumentAdapter<br/>(content provider)"]
    end

    subgraph "System Service Layer"
        PMS["PrintManagerService<br/>(SystemService)"]
        PMI["PrintManagerImpl<br/>(IPrintManager.Stub)"]
        US["UserState<br/>(per-user state)"]
    end

    subgraph "Spooler Layer"
        RPS["RemotePrintSpooler<br/>(proxy)"]
        SPOOLER["PrintSpooler<br/>(com.android.printspooler)"]
    end

    subgraph "Print Service Layer"
        RPSS["RemotePrintService<br/>(proxy)"]
        PS["PrintService<br/>(plugin)"]
        PDS["PrinterDiscoverySession"]
    end

    subgraph "Hardware / Output"
        PRINTER["Physical Printer"]
        PDF["PDF Output"]
    end

    APP --> PM
    APP --> PDA
    PM -->|"Binder IPC"| PMI
    PMI --> US
    US --> RPS
    US --> RPSS
    RPS -->|"bind service"| SPOOLER
    RPSS -->|"bind service"| PS
    PS --> PDS
    PS --> PRINTER
    SPOOLER --> PDF
```

**Key source files:**

| File | Path | Purpose |
|------|------|---------|
| `PrintManager.java` | `frameworks/base/core/java/android/print/` | Client-facing API |
| `PrintDocumentAdapter.java` | Same directory | App document rendering contract |
| `PrintJobInfo.java` | Same directory | Print job state representation |
| `PrintJob.java` | Same directory | Print job handle for apps |
| `PrintAttributes.java` | Same directory | Page size, margins, color mode |
| `PrinterInfo.java` | Same directory | Printer description (name, status, capabilities, setup intent) |
| `flags/flags.aconfig` | Same directory | `android.print.flags` aconfig declarations |
| `PrintedPdfDocument.java` | `frameworks/base/core/java/android/print/pdf/` | PDF rendering helper |
| `PrintService.java` | `frameworks/base/core/java/android/printservice/` | Print service plugin base class |
| `PrinterDiscoverySession.java` | Same directory | Printer discovery lifecycle |
| `PrintManagerService.java` | `frameworks/base/services/print/java/com/android/server/print/` | System service entry point |
| `UserState.java` | Same directory | Per-user print state management |
| `RemotePrintSpooler.java` | Same directory | Spooler process proxy |
| `RemotePrintService.java` | Same directory | Print service process proxy |
| `PrintSpoolerService.java` | `frameworks/base/packages/PrintSpooler/src/com/android/printspooler/model/` | Spooler-process job store |
| `flags/flags.aconfig` | `frameworks/base/packages/PrintSpooler/` | `com.android.printspooler.flags` aconfig declarations |

---

## 61.2 PrintManager -- The Client API

`PrintManager` is the system service accessor for printing capabilities. It
is annotated as a `@SystemService` and requires `PackageManager.FEATURE_PRINTING`:

```java
// frameworks/base/core/java/android/print/PrintManager.java
@SystemService(Context.PRINT_SERVICE)
@RequiresFeature(PackageManager.FEATURE_PRINTING)
public final class PrintManager {
    public static final String PRINT_SPOOLER_PACKAGE_NAME = "com.android.printspooler";
```

### 61.2.1 Starting a Print Job

An application initiates printing by calling `PrintManager.print()` from an
Activity:

```java
// Application code
PrintManager printManager = (PrintManager) getSystemService(Context.PRINT_SERVICE);
PrintJob job = printManager.print("My Document", new MyPrintDocumentAdapter(), null);
```

The `print()` method:

1. Creates a `PrintDocumentAdapterDelegate` proxy for cross-process communication
2. Sends the print request to `PrintManagerImpl` via Binder IPC
3. Reads the `IntentSender` the system returns under `EXTRA_PRINT_DIALOG_INTENT`
   and starts the print UI (from the `com.android.printspooler` package) with it
4. Returns a `PrintJob` handle for tracking state, or `null` if printing is
   unavailable

The Android 17 implementation hardens this path. `print()` builds an
`ActivityOptions` with
`MODE_BACKGROUND_ACTIVITY_START_ALLOWED` so the spooler dialog is allowed to
launch from the print request, and it now catches `ActivityNotFoundException`
when the dialog activity cannot be resolved, returning `null` (the documented
failure mode) instead of leaking the exception to the caller:

```java
// frameworks/base/core/java/android/print/PrintManager.java
try {
    ActivityOptions activityOptions = ActivityOptions.makeBasic()
            .setPendingIntentBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED);
    mContext.startIntentSender(intent, null, 0, 0, 0, activityOptions.toBundle());
    return new PrintJob(printJob, this);
} catch (SendIntentException sie) {
    Log.e(LOG_TAG, "Couldn't start print job config activity.", sie);
} catch (ActivityNotFoundException anfe) {
    Log.e(LOG_TAG, "Print preview activity not found: ", anfe);
}
return null;
```

### 61.2.2 Querying Print Jobs

Applications can query their own print jobs (but not those of other apps):

```java
// Get all print jobs for this app
List<PrintJob> jobs = printManager.getPrintJobs();

// Check specific job state
for (PrintJob job : jobs) {
    PrintJobInfo info = job.getInfo();
    if (info.getState() == PrintJobInfo.STATE_COMPLETED) {
        // Job finished successfully
    }
}
```

### 61.2.3 Print Job State Change Listeners

Apps can register for state change notifications:

```java
// frameworks/base/core/java/android/print/PrintManager.java
private static final int MSG_NOTIFY_PRINT_JOB_STATE_CHANGED = 1;
```

The listener mechanism uses a handler-based callback to deliver state changes
on the main thread.

### 61.2.4 Service Selection Constants

```java
// frameworks/base/core/java/android/print/PrintManager.java
public static final int ENABLED_SERVICES = 1 << 0;
public static final int DISABLED_SERVICES = 1 << 1;
public static final int ALL_SERVICES = ENABLED_SERVICES | DISABLED_SERVICES;
```

These constants are used by system-level callers to query which print services
are currently enabled or disabled in Settings.

---

## 61.3 PrintDocumentAdapter -- The Rendering Contract

`PrintDocumentAdapter` is the abstract class that applications implement to
provide content for printing. It defines a strict lifecycle contract between
the application and the print framework.

### 61.3.1 Lifecycle

```mermaid
stateDiagram-v2
    [*] --> onStart: Print initiated
    onStart --> onLayout: Print attributes provided
    onLayout --> onWrite: Layout done, content changed
    onLayout --> onLayout: Attributes changed
    onWrite --> onLayout: Attributes changed
    onWrite --> onFinish: All pages written
    onLayout --> onFinish: User cancels
    onFinish --> [*]: Resources released
```

The lifecycle callbacks:

```java
// frameworks/base/core/java/android/print/PrintDocumentAdapter.java
public abstract class PrintDocumentAdapter {
    public static final String EXTRA_PRINT_PREVIEW = "EXTRA_PRINT_PREVIEW";

    // 1. Called once when printing starts
    public void onStart() { /* stub */ }

    // 2. Called when print attributes change (page size, density, etc.)
    public abstract void onLayout(PrintAttributes oldAttributes,
            PrintAttributes newAttributes,
            CancellationSignal cancellationSignal,
            LayoutResultCallback callback,
            Bundle extras);

    // 3. Called to render specific pages as PDF
    public abstract void onWrite(PageRange[] pages,
            ParcelFileDescriptor destination,
            CancellationSignal cancellationSignal,
            WriteResultCallback callback);

    // 4. Called once when printing finishes
    public void onFinish() { /* stub */ }
}
```

### 61.3.2 The Layout-Write Protocol

The interaction between the system and the adapter follows a callback protocol:

```mermaid
sequenceDiagram
    participant System as Print System
    participant Adapter as PrintDocumentAdapter
    participant Callback as LayoutResultCallback

    System->>Adapter: onStart()
    System->>Adapter: onLayout(oldAttrs, newAttrs, cancel, callback, extras)

    alt Layout succeeds
        Adapter->>Callback: onLayoutFinished(info, contentChanged=true)
        System->>Adapter: onWrite(pages, fd, cancel, writeCallback)
        Note over Adapter: Render pages as PDF to fd
        Adapter->>System: writeCallback.onWriteFinished(writtenPages)
    else Layout fails
        Adapter->>Callback: onLayoutFailed("reason")
    else Layout cancelled
        Adapter->>Callback: onLayoutCancelled()
    end

    System->>Adapter: onFinish()
```

Key rules:

- `onLayout()` is **not** complete until one callback method is invoked
- `onWrite()` is **not** complete until one callback method is invoked
- No other lifecycle method will be called until the current one completes
- The adapter **must** close the `ParcelFileDescriptor` passed to `onWrite()`
- The `extras` bundle contains `EXTRA_PRINT_PREVIEW` to indicate preview mode

### 61.3.3 Cancellation

The `CancellationSignal` parameter allows the system to request cancellation:

```java
cancellationSignal.setOnCancelListener(new OnCancelListener() {
    @Override
    public void onCancel() {
        // Stop layout or write work
    }
});
```

This is important when the user changes print options during an ongoing
layout -- the system cancels the current layout and requests a new one.

### 61.3.4 PrintDocumentInfo

After layout, the adapter reports document metadata:

```java
PrintDocumentInfo info = new PrintDocumentInfo.Builder("document.pdf")
        .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
        .setPageCount(pageCount)
        .build();
callback.onLayoutFinished(info, contentChanged);
```

The `contentChanged` flag is critical: if `false`, the system can reuse
previously rendered pages and skip the `onWrite()` call.

---

## 61.4 Print Job Lifecycle

A print job transitions through seven states, tracked by `PrintJobInfo`:

### 61.4.1 State Constants

```java
// frameworks/base/core/java/android/print/PrintJobInfo.java
public static final int STATE_CREATED = 1;   // Being created in print UI
public static final int STATE_QUEUED = 2;    // Ready for processing
public static final int STATE_STARTED = 3;   // Being printed
public static final int STATE_BLOCKED = 4;   // Temporarily blocked
public static final int STATE_COMPLETED = 5; // Successfully printed (terminal)
public static final int STATE_FAILED = 6;    // Printing failed
public static final int STATE_CANCELED = 7;  // Canceled (terminal)
```

### 61.4.2 State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED: print called
    CREATED --> QUEUED: User confirms<br/>in print UI

    QUEUED --> STARTED: PrintService starts<br/>processing
    QUEUED --> FAILED: Processing fails
    QUEUED --> CANCELED: User cancels

    STARTED --> COMPLETED: Print succeeds
    STARTED --> FAILED: Print fails
    STARTED --> CANCELED: User cancels
    STARTED --> BLOCKED: Printer problem<br/>paper jam, etc.

    BLOCKED --> STARTED: Problem resolved
    BLOCKED --> FAILED: Unrecoverable
    BLOCKED --> CANCELED: User cancels

    FAILED --> STARTED: User restarts
    FAILED --> CANCELED: User cancels

    COMPLETED --> [*]
    CANCELED --> [*]
```

### 61.4.3 Internal State Groupings

The system uses aggregate state constants for filtering:

| Constant | States Included | Purpose |
|----------|----------------|---------|
| `STATE_ANY` | All states | No filtering |
| `STATE_ANY_VISIBLE_TO_CLIENTS` | All except `CREATED` | Visible to the creating app |
| `STATE_ANY_ACTIVE` | `CREATED`, `QUEUED`, `STARTED`, `BLOCKED` | Non-terminal states |
| `STATE_ANY_SCHEDULED` | `QUEUED`, `STARTED`, `BLOCKED` | Delivered to print service |

### 61.4.4 PrintJob Wrapper

The `PrintJob` class provides a convenient wrapper for applications:

```java
// frameworks/base/core/java/android/print/PrintJob.java
public final class PrintJob {
    private final @NonNull PrintManager mPrintManager;
    private @NonNull PrintJobInfo mCachedInfo;

    public void cancel() {
        final int state = getInfo().getState();
        if (state == PrintJobInfo.STATE_QUEUED
                || state == PrintJobInfo.STATE_STARTED
                || state == PrintJobInfo.STATE_BLOCKED
                || state == PrintJobInfo.STATE_FAILED) {
            mPrintManager.cancelPrintJob(mCachedInfo.getId());
        }
    }
```

The cached `PrintJobInfo` is refreshed on each `getInfo()` call for active
jobs but returned directly for terminal states (completed/canceled), since
those cannot change.

---

## 61.5 PrintAttributes -- Describing Print Output

`PrintAttributes` encapsulates how content should be formatted for printing:

### 61.5.1 Media Size

Media sizes define page dimensions using the standard `MediaSize` class:

```java
// frameworks/base/core/java/android/print/PrintAttributes.java
// Standard sizes include:
MediaSize.ISO_A4       // 210 x 297mm
MediaSize.NA_LETTER    // 8.5 x 11 inches
MediaSize.NA_LEGAL     // 8.5 x 14 inches
MediaSize.JIS_B5       // 182 x 257mm
```

Sizes are stored in mils (thousandths of an inch) internally.

### 61.5.2 Color and Duplex Modes

```java
// Color modes
public static final int COLOR_MODE_MONOCHROME = 1; // Black & white
public static final int COLOR_MODE_COLOR = 2;      // Full color

// Duplex modes
public static final int DUPLEX_MODE_NONE = 1;       // Single-sided
public static final int DUPLEX_MODE_LONG_EDGE = 2;  // Book-style
public static final int DUPLEX_MODE_SHORT_EDGE = 4;  // Notepad-style
```

### 61.5.3 Resolution and Margins

`Resolution` defines DPI (dots per inch) for horizontal and vertical axes.
`Margins` define minimum margins in mils on all four sides.

---

## 61.6 PDF Rendering with PrintedPdfDocument

`PrintedPdfDocument` is a helper class that simplifies creating PDF output
from Android's Canvas-based graphics API:

```java
// frameworks/base/core/java/android/print/pdf/PrintedPdfDocument.java
public class PrintedPdfDocument extends PdfDocument {
    private static final int MILS_PER_INCH = 1000;
    private static final int POINTS_IN_INCH = 72;

    private final int mPageWidth;
    private final int mPageHeight;
    private final Rect mContentRect;
```

### 61.6.1 Coordinate System

The class converts between three coordinate systems:

```mermaid
flowchart LR
    subgraph "Input"
        MILS["PrintAttributes<br/>(mils: 1/1000 inch)"]
    end

    subgraph "Conversion"
        CALC["mils / 1000 * 72<br/>= PDF points"]
    end

    subgraph "Output"
        POINTS["PdfDocument<br/>(points: 1/72 inch)"]
    end

    MILS --> CALC --> POINTS
```

For an 8.5 x 11 inch letter page:

- Width: 8500 mils -> 612 points
- Height: 11000 mils -> 792 points

### 61.6.2 Usage Pattern

```java
// Typical implementation in a PrintDocumentAdapter
@Override
public void onWrite(PageRange[] pages, ParcelFileDescriptor destination,
        CancellationSignal cancel, WriteResultCallback callback) {

    PrintedPdfDocument document = new PrintedPdfDocument(context, printAttributes);

    for (int pageNum : pagesToWrite) {
        PdfDocument.Page page = document.startPage(pageNum);

        // Get the Canvas and draw content
        Canvas canvas = page.getCanvas();
        drawPageContent(canvas, pageNum);

        document.finishPage(page);
    }

    // Write to the file descriptor
    document.writeTo(new FileOutputStream(destination.getFileDescriptor()));
    document.close();

    callback.onWriteFinished(new PageRange[] { PageRange.ALL_PAGES });
}
```

### 61.6.3 Content Rect

The content rectangle accounts for margins, giving the drawable area:

```java
// frameworks/base/core/java/android/print/pdf/PrintedPdfDocument.java
Margins minMargins = attributes.getMinMargins();
final int marginLeft = (int) (((float) minMargins.getLeftMils() / MILS_PER_INCH)
        * POINTS_IN_INCH);
// ... similar for top, right, bottom
mContentRect = new Rect(marginLeft, marginTop,
        mPageWidth - marginRight, mPageHeight - marginBottom);
```

---

## 61.7 PrintManagerService -- The System Service

`PrintManagerService` wraps the `PrintManagerImpl` Binder service and integrates
with the `SystemService` lifecycle:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
public final class PrintManagerService extends SystemService {
    private final PrintManagerImpl mPrintManagerImpl;

    @Override
    public void onStart() {
        publishBinderService(Context.PRINT_SERVICE, mPrintManagerImpl);
    }

    @Override
    public void onUserUnlocking(@NonNull TargetUser user) {
        mPrintManagerImpl.handleUserUnlocked(user.getUserIdentifier());
    }

    @Override
    public void onUserStopping(@NonNull TargetUser user) {
        mPrintManagerImpl.handleUserStopped(user.getUserIdentifier());
    }
}
```

### 61.7.1 Multi-User Architecture

Each user gets an independent `UserState` instance that manages print services,
the spooler connection, and printer discovery:

```mermaid
graph TB
    subgraph "PrintManagerImpl"
        LOCK["Object mLock"]
        STATES["SparseArray<UserState><br/>mUserStates"]
    end

    subgraph "User 0 State"
        US0["UserState"]
        SPOOLER0["RemotePrintSpooler"]
        SERVICES0["RemotePrintService[]<br/>(active services)"]
    end

    subgraph "User 10 State"
        US10["UserState"]
        SPOOLER10["RemotePrintSpooler"]
        SERVICES10["RemotePrintService[]<br/>(active services)"]
    end

    STATES -->|"userId=0"| US0
    STATES -->|"userId=10"| US10
    US0 --> SPOOLER0
    US0 --> SERVICES0
    US10 --> SPOOLER10
    US10 --> SERVICES10
```

`UserState` is created on user unlock and destroyed on user stop:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
class PrintManagerImpl extends IPrintManager.Stub {
    private static final int BACKGROUND_USER_ID = -10;
    private final SparseArray<UserState> mUserStates = new SparseArray<>();
```

### 61.7.2 Permission Enforcement

The `print()` method in `PrintManagerImpl` validates:

1. The adapter is non-null
2. Printing is enabled (not disabled by device policy)
3. The calling user is the current foreground user (or a profile of it)

Printing is gated by the `UserManager.DISALLOW_PRINTING` user restriction,
which `DevicePolicyManager` sets when an admin disables printing:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
private boolean isPrintingEnabled() {
    return !mUserManager.hasUserRestriction(UserManager.DISALLOW_PRINTING,
            Binder.getCallingUserHandle());
}
```

When printing is disabled, `print()` fetches the human-readable reason through
`DevicePolicyManagerInternal.getPrintingDisabledReasonForUser()`, shows it in a
toast, drives the adapter through `start()`/`finish()` so the app's resources
are released, and returns `null` without creating a job.

### 61.7.3 Content Observers and Broadcast Receivers

`PrintManagerImpl` registers:

- **Content observers** on `Settings.Secure.DISABLED_PRINT_SERVICES` to track
  which print services the user has *disabled* in Settings (see Section 61.8.2 for
  why Android tracks the disabled set rather than the enabled set)

- **Package monitors** to detect installation, removal, or updates of print
  service packages

---

## 61.8 UserState -- Per-User Print Management

`UserState` is the core per-user coordinator. It implements three callback
interfaces:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
final class UserState implements
        PrintSpoolerCallbacks,       // Spooler lifecycle events
        PrintServiceCallbacks,       // Print service events
        RemotePrintServiceRecommendationServiceCallbacks {  // Recommendations
```

### 61.8.1 Internal State

```java
// Active (bound) print services
private final ArrayMap<ComponentName, RemotePrintService> mActiveServices;

// All installed print service packages
private final List<PrintServiceInfo> mInstalledServices;

// Disabled print services
private final Set<ComponentName> mDisabledServices;

// Cache of print jobs visible to apps
private final PrintJobForAppCache mPrintJobForAppCache;

// Printer discovery session mediator
private PrinterDiscoverySessionMediator mPrinterDiscoverySession;

// Spooler connection
private final RemotePrintSpooler mSpooler;
```

### 61.8.2 Service Discovery

When a user is unlocked, `UserState` discovers print services by querying
`PackageManager` for services with the action
`android.printservice.PrintService`:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
private final Intent mQueryIntent =
        new Intent(android.printservice.PrintService.SERVICE_INTERFACE);
```

Since Android N, the system persists the *disabled* set rather than the enabled
set: every installed print service is considered enabled unless its
`ComponentName` appears in `Settings.Secure.DISABLED_PRINT_SERVICES` (a
colon-separated list). `readDisabledPrintServicesLocked()` parses that setting
into `mDisabledServices`, and `writeDisabledPrintServicesLocked()` persists it.
`Settings.Secure.ENABLED_PRINT_SERVICES` survives only as a one-time migration
input: `upgradePersistentStateIfNeeded()` reads any legacy enabled list,
converts it into the equivalent disabled set, and then clears
`ENABLED_PRINT_SERVICES` to `null` so the upgrade never runs again:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
// Pre N we store the enabled services, in N and later we store the disabled services.
// Hence if enabledSettingValue is still set, we need to upgrade.
if (enabledSettingValue != null) {
    // ... compute disabledServices = installed - enabled ...
    writeDisabledPrintServicesLocked(disabledServices);
    Settings.Secure.putStringForUser(mContext.getContentResolver(),
            Settings.Secure.ENABLED_PRINT_SERVICES, null, mUserId);
}
```

### 61.8.3 Service Lifecycle Management

Active services are managed through `RemotePrintService` proxies:

```mermaid
flowchart TB
    UNLOCK["User Unlocked"]
    QUERY["Query PackageManager<br/>for PrintService implementations"]
    ENABLED["Filter out Settings.Secure<br/>DISABLED_PRINT_SERVICES"]
    BIND["Bind to enabled services<br/>(RemotePrintService)"]
    ACTIVE["Service active:<br/>can discover printers<br/>and process jobs"]

    STOP["User Stopped"]
    UNBIND["Unbind all services"]
    DESTROY["Destroy UserState"]

    UNLOCK --> QUERY --> ENABLED --> BIND --> ACTIVE
    STOP --> UNBIND --> DESTROY
```

When a service crashes, `RemotePrintService` receives the death notification
and schedules a restart after 500ms:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
private static final int SERVICE_RESTART_DELAY_MILLIS = 500;
```

---

## 61.9 PrintService -- The Plugin API

`PrintService` is the base class for print service plugins. Third-party apps
(e.g., HP Print Service, Mopria Print Service) extend this class to support
specific printers.

### 61.9.1 Service Declaration

A print service must declare itself in the manifest with specific permissions
and intent filters:

```xml
<service android:name=".MyPrintService"
         android:permission="android.permission.BIND_PRINT_SERVICE">
    <intent-filter>
        <action android:name="android.printservice.PrintService" />
    </intent-filter>
    <meta-data android:name="android.printservice"
               android:resource="@xml/printservice" />
</service>
```

The `BIND_PRINT_SERVICE` permission ensures only the system can bind to it.

### 61.9.2 Key Callbacks

```java
// frameworks/base/core/java/android/printservice/PrintService.java
public abstract class PrintService extends Service {

    // Called when the system needs to discover printers
    protected abstract PrinterDiscoverySession onCreatePrinterDiscoverySession();

    // Called when a print job is queued and ready for processing
    protected abstract void onPrintJobQueued(PrintJob printJob);

    // Called when the user requests cancellation of a print job
    protected abstract void onRequestCancelPrintJob(PrintJob printJob);

    // Called after the system binds
    protected void onConnected() { }

    // Called before the system unbinds
    protected void onDisconnected() { }
}
```

### 61.9.3 Print Job Processing Flow

```mermaid
sequenceDiagram
    participant User as User
    participant SpUI as Print UI
    participant Spooler as PrintSpooler
    participant PMS as PrintManagerService
    participant PS as PrintService

    User->>SpUI: Select printer & confirm
    SpUI->>Spooler: Spool document (PDF)
    Spooler->>PMS: Job state = QUEUED
    PMS->>PS: onPrintJobQueued(job)

    PS->>PS: job.start()
    Note over PS: State = STARTED

    PS->>PS: Read job.getDocument().getData()
    PS->>PS: Send data to printer

    alt Success
        PS->>PS: job.complete()
        Note over PS: State = COMPLETED
    else Failure
        PS->>PS: job.fail("reason")
        Note over PS: State = FAILED
    else Blocked
        PS->>PS: job.block("paper jam")
        Note over PS: State = BLOCKED
    end
```

### 61.9.4 Accessing Print Data

The print service accesses the spooled document through `PrintDocument`:

```java
// In the PrintService
@Override
protected void onPrintJobQueued(PrintJob printJob) {
    printJob.start();

    PrintDocument document = printJob.getDocument();
    InputStream data = new FileInputStream(
            document.getData().getFileDescriptor());

    // data is a PDF file -- send to printer
    sendToPrinter(data, printJob.getInfo());

    printJob.complete();
}
```

The data is always a PDF file, regardless of the original content format.

---

## 61.10 Printer Discovery

Printer discovery is managed through `PrinterDiscoverySession`, which has
its own lifecycle independent of the print service.

### 61.10.1 Discovery Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: onCreatePrinterDiscoverySession
    Created --> Discovering: onStartPrinterDiscovery
    Discovering --> Discovering: addPrinters / removePrinters
    Discovering --> Idle: onStopPrinterDiscovery
    Idle --> Discovering: onStartPrinterDiscovery
    Idle --> Destroyed: onDestroy
    Discovering --> Destroyed: onDestroy
    Destroyed --> [*]
```

### 61.10.2 Key Methods

```java
// frameworks/base/core/java/android/printservice/PrinterDiscoverySession.java
public abstract class PrinterDiscoverySession {

    // System requests to start discovering printers
    public abstract void onStartPrinterDiscovery(List<PrinterId> priorityList);

    // System requests to stop discovering
    public abstract void onStopPrinterDiscovery();

    // System requests validation of specific printers
    public abstract void onValidatePrinters(List<PrinterId> printerIds);

    // System is interested in real-time updates for a printer
    public abstract void onStartPrinterStateTracking(PrinterId printerId);

    // System no longer needs real-time updates
    public abstract void onStopPrinterStateTracking(PrinterId printerId);

    // Session is being destroyed
    public abstract void onDestroy();

    // Services call these to report printers
    public final void addPrinters(List<PrinterInfo> printers);
    public final void removePrinters(List<PrinterId> printerIds);
}
```

### 61.10.3 PrinterInfo and Capabilities

Printers are described using `PrinterInfo`:

```java
PrinterInfo printer = new PrinterInfo.Builder(printerId, "My Printer",
        PrinterInfo.STATUS_IDLE)
    .setDescription("Color Laser Printer")
    .setCapabilities(capabilities)
    .build();
```

`PrinterCapabilitiesInfo` describes what a printer can do:

```mermaid
graph LR
    subgraph "PrinterCapabilitiesInfo"
        MS["Media Sizes<br/>(A4, Letter, etc.)"]
        RES["Resolutions<br/>(300dpi, 600dpi)"]
        CM["Color Modes<br/>(Mono, Color)"]
        DM["Duplex Modes<br/>(None, Long, Short)"]
        MG["Min Margins"]
    end
```

### 61.10.4 Priority List

The `priorityList` parameter in `onStartPrinterDiscovery()` contains printers
that should be discovered first -- typically printers the user has used
recently. This allows print services to prioritize network discovery for
known printers.

### 61.10.5 Printer State Tracking

When the user selects a printer in the print UI, the system calls
`onStartPrinterStateTracking()` for that printer. The service should then
provide real-time status updates (idle, busy, unavailable) and capabilities
if not yet provided. This lazy capability loading avoids querying all
discovered printers upfront.

---

## 61.11 The Print Spooler

The print spooler (`com.android.printspooler`) is a separate system process
that manages the print queue and hosts the print preview UI.

### 61.11.1 RemotePrintSpooler

`RemotePrintSpooler` is the system service's proxy to the spooler process:

```java
// frameworks/base/services/print/java/com/android/server/print/RemotePrintSpooler.java
final class RemotePrintSpooler {
    private static final long BIND_SPOOLER_SERVICE_TIMEOUT =
            (Build.IS_ENG) ? 120000 : 10000;

    private final ServiceConnection mServiceConnection = new MyServiceConnection();
    private IPrintSpooler mRemoteInstance;
```

### 61.11.2 Timed Remote Calls

All calls to the spooler use `TimedRemoteCaller` to enforce timeouts:

```java
// Individual timed callers for each operation
private final GetPrintJobInfosCaller mGetPrintJobInfosCaller;
private final GetPrintJobInfoCaller mGetPrintJobInfoCaller;
private final SetPrintJobStateCaller mSetPrintJobStatusCaller;
private final SetPrintJobTagCaller mSetPrintJobTagCaller;
```

The binding timeout is 10 seconds on production builds, 120 seconds on
engineering builds (to accommodate debugger attachment).

### 61.11.3 Spooler Binding Lifecycle

```mermaid
sequenceDiagram
    participant US as UserState
    participant RPS as RemotePrintSpooler
    participant SP as PrintSpooler (separate process)

    US->>RPS: getPrintJobInfos()
    RPS->>RPS: ensureBound()

    alt Not bound
        RPS->>SP: bindService(Intent)
        Note over RPS: Wait up to 10s
        SP-->>RPS: onServiceConnected()
    end

    RPS->>SP: IPrintSpooler.getPrintJobInfos()
    SP-->>RPS: results
    RPS-->>US: results

    Note over RPS: After idle period
    RPS->>SP: unbindService()
```

### 61.11.4 Spooler Callbacks

The spooler notifies the system service of state changes through
`PrintSpoolerCallbacks`:

```java
// frameworks/base/services/print/java/com/android/server/print/RemotePrintSpooler.java
public static interface PrintSpoolerCallbacks {
    public void onPrintJobQueued(PrintJobInfo printJob);
    public void onAllPrintJobsForServiceHandled(ComponentName printService);
    public void onPrintJobStateChanged(PrintJobInfo printJob);
}
```

---

## 61.12 RemotePrintService -- Service Process Proxy

`RemotePrintService` manages the lifecycle of a bound print service:

```java
// frameworks/base/services/print/java/com/android/server/print/RemotePrintService.java
final class RemotePrintService implements DeathRecipient {
    private final List<Runnable> mPendingCommands = new ArrayList<>();
    private IPrintService mPrintService;
    private boolean mBinding;
    private boolean mHasActivePrintJobs;
    private boolean mHasPrinterDiscoverySession;
```

### 61.12.1 Deferred Commands

If the service is not yet bound when a command arrives, it is added to
`mPendingCommands` and executed after binding completes:

```mermaid
flowchart TB
    CMD["Command arrives"]
    BOUND{"Service<br/>bound?"}
    EXEC["Execute immediately"]
    QUEUE["Add to mPendingCommands"]
    BIND["Initiate binding"]
    CONNECTED["onServiceConnected()"]
    FLUSH["Execute all pending commands"]

    CMD --> BOUND
    BOUND -->|"Yes"| EXEC
    BOUND -->|"No"| QUEUE
    QUEUE --> BIND
    BIND --> CONNECTED
    CONNECTED --> FLUSH
```

### 61.12.2 Death Handling

When a print service process dies:

```java
// frameworks/base/services/print/java/com/android/server/print/RemotePrintService.java
// implements DeathRecipient
```

The `RemotePrintService` detects the death, notifies `UserState` through
`PrintServiceCallbacks.onServiceDied()`, and the `UserState` schedules
a restart after 500ms.

### 61.12.3 Tracked Printers

The proxy tracks which printers are being actively monitored:

```java
@GuardedBy("mLock")
private List<PrinterId> mTrackedPrinterList;
```

This allows the proxy to re-request printer state tracking after a service
restart, providing seamless recovery from service crashes.

---

## 61.13 The Complete Print Flow

Here is the end-to-end flow from a user pressing "Print" in an application
to the document arriving at the printer:

```mermaid
sequenceDiagram
    participant User
    participant App as Application
    participant PM as PrintManager
    participant PMS as PrintManagerService
    participant US as UserState
    participant SP as PrintSpooler
    participant PUI as Print UI
    participant PDA as PrintDocumentAdapter
    participant RPS as RemotePrintService
    participant PS as PrintService
    participant Printer

    User->>App: Press "Print"
    App->>PM: print("doc", adapter, attrs)
    PM->>PMS: Binder: print()
    PMS->>US: print()
    US->>SP: createPrintJob()
    SP->>PUI: Launch print UI

    PUI->>PUI: Show printer selection

    Note over PUI,PS: Printer Discovery
    US->>RPS: createPrinterDiscoverySession()
    RPS->>PS: onCreatePrinterDiscoverySession()
    PS->>PS: Discover printers (mDNS, etc.)
    PS-->>RPS: addPrinters([...])
    RPS-->>PUI: Show discovered printers

    User->>PUI: Select printer & options

    Note over PUI,PDA: Document Rendering
    PUI->>PDA: onLayout(attributes)
    PDA-->>PUI: onLayoutFinished(info)
    PUI->>PDA: onWrite(pages, fd)
    PDA->>PDA: Render pages as PDF
    PDA-->>PUI: onWriteFinished(pages)

    User->>PUI: Press "Print" button

    Note over SP,Printer: Print Execution
    SP->>SP: Spool PDF document
    SP->>PMS: Job state = QUEUED
    PMS->>US: onPrintJobQueued()
    US->>RPS: onPrintJobQueued(job)
    RPS->>PS: onPrintJobQueued(job)

    PS->>PS: job.start()
    PS->>PS: Read PDF from job.getDocument()
    PS->>Printer: Send print data
    Printer-->>PS: Print complete
    PS->>PS: job.complete()
```

---

## 61.14 The print() Method Internals

The `UserState.print()` method reveals the internal mechanics of job creation:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
public Bundle print(@NonNull String printJobName, @NonNull IPrintDocumentAdapter adapter,
        @Nullable PrintAttributes attributes, @NonNull String packageName, int appId) {
    // Create print job place holder.
    final PrintJobInfo printJob = new PrintJobInfo();
    printJob.setId(new PrintJobId());
    printJob.setAppId(appId);
    printJob.setLabel(printJobName);
    printJob.setAttributes(attributes);
    printJob.setState(PrintJobInfo.STATE_CREATED);
    printJob.setCopies(1);
    printJob.setCreationTime(System.currentTimeMillis());

    // Track this job so we can forget it when the creator dies.
    if (!mPrintJobForAppCache.onPrintJobCreated(adapter.asBinder(), appId, printJob)) {
        return null; // Client is dead
    }

    Intent intent = new Intent(PrintManager.ACTION_PRINT_DIALOG);
    intent.setData(Uri.fromParts("printjob", printJob.getId().flattenToString(), null));
    intent.putExtra(PrintManager.EXTRA_PRINT_DOCUMENT_ADAPTER, adapter.asBinder());
    intent.putExtra(PrintManager.EXTRA_PRINT_JOB, printJob);
    intent.putExtra(Intent.EXTRA_PACKAGE_NAME, packageName);

    ActivityOptions activityOptions = ActivityOptions.makeBasic()
            .setPendingIntentCreatorBackgroundActivityStartMode(
                    ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_DENIED);
    IntentSender intentSender = PendingIntent.getActivityAsUser(
            mContext, 0, intent, PendingIntent.FLAG_ONE_SHOT
                    | PendingIntent.FLAG_CANCEL_CURRENT | PendingIntent.FLAG_IMMUTABLE,
            activityOptions.toBundle(), new UserHandle(mUserId)).getIntentSender();

    Bundle result = new Bundle();
    result.putParcelable(PrintManager.EXTRA_PRINT_JOB, printJob);
    result.putParcelable(PrintManager.EXTRA_PRINT_DIALOG_INTENT, intentSender);
    return result;
}
```

Key implementation details:

1. **Death tracking**: The adapter Binder is monitored via `PrintJobForAppCache` --
   if the creating app dies, its print jobs are cleaned up

2. **PendingIntent**: The print dialog is launched through a `PendingIntent`
   wrapped in a Bundle under `EXTRA_PRINT_DIALOG_INTENT`. The client
   (`PrintManager.print()` in Section 61.2.1) reads that `IntentSender` and starts
   it, so the dialog runs with the correct security context across process
   boundaries

3. **Background activity restriction**: The `PendingIntent` is built with
   `setPendingIntentCreatorBackgroundActivityStartMode(MODE_BACKGROUND_ACTIVITY_START_DENIED)`,
   so the *creating* app cannot use this intent to launch background activities

4. **Initial state**: Every print job starts as `STATE_CREATED` with 1 copy

### 61.14.1 PrintJobForAppCache

When applications create print jobs, they are tracked in a cache keyed by
app ID. This serves two purposes:

- **Job fusion**: The cache merges with spooler data in `getPrintJobInfos()`
  to provide a complete view. The spooler does not store terminal-state jobs,
  while the cache retains them until the app dies

- **Tag stripping**: Tags and advanced options are stripped when returning
  jobs to apps -- these are only visible to print services

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
public List<PrintJobInfo> getPrintJobInfos(int appId) {
    List<PrintJobInfo> cachedPrintJobs = mPrintJobForAppCache.getPrintJobs(appId);
    // Note that the print spooler is not storing print jobs that
    // are in a terminal state as it is non-trivial to properly update
    // the spooler state for when to forget print jobs in terminal state.
    // Therefore, we fuse the cached print jobs for running apps (some
    // jobs are in a terminal state) with the ones that the print
    // spooler knows about (some jobs are being processed).
```

### 61.14.2 Cancel and Restart Flow

Canceling a print job involves both the spooler and the print service:

```mermaid
sequenceDiagram
    participant App
    participant US as UserState
    participant SP as RemotePrintSpooler
    participant PS as RemotePrintService

    App->>US: cancelPrintJob(jobId)
    US->>SP: setPrintJobCancelling(jobId, true)

    alt Job is not FAILED
        US->>PS: onRequestCancelPrintJob(jobInfo)
        Note over PS: Best-effort cancel
        PS->>SP: setPrintJobState(CANCELED)
    else Job is FAILED
        US->>SP: setPrintJobState(CANCELED)
        Note over US: No service cooperation needed
    end
```

Restarting a failed job simply transitions it back to `QUEUED`:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
public void restartPrintJob(@NonNull PrintJobId printJobId, int appId) {
    PrintJobInfo printJobInfo = getPrintJobInfo(printJobId, appId);
    if (printJobInfo == null || printJobInfo.getState() != PrintJobInfo.STATE_FAILED) {
        return;
    }
    mSpooler.setPrintJobState(printJobId, PrintJobInfo.STATE_QUEUED, null);
}
```

### 61.14.3 Job Routing to Services

When the spooler notifies that a job is queued, `UserState` routes it to the
correct print service based on the printer's `ComponentName`:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
@Override
public void onPrintJobQueued(PrintJobInfo printJob) {
    ComponentName printServiceName = printJob.getPrinterId().getServiceName();
    RemotePrintService service = mActiveServices.get(printServiceName);

    if (service != null) {
        service.onPrintJobQueued(printJob);
    } else {
        // The service is no longer enabled
        mSpooler.setPrintJobState(printJob.getId(), PrintJobInfo.STATE_FAILED,
                mContext.getString(R.string.reason_service_unavailable));
    }
}
```

If the targeted print service has been disabled between when the user selected
the printer and when the job was queued, the job immediately fails with
"service unavailable."

---

## 61.15 PrintManagerImpl Binder Service

The `PrintManagerImpl` inner class handles all Binder calls with careful
security enforcement:

### 61.15.1 User Resolution

Every API call resolves the calling user and validates permissions:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
final int resolvedUserId = resolveCallingUserEnforcingPermissions(userId);
final int resolvedAppId;
final UserState userState;
synchronized (mLock) {
    // Only the current group members can start new print jobs.
    if (resolveCallingProfileParentLocked(resolvedUserId) != getCurrentUserId()) {
        return null;
    }
    resolvedAppId = resolveCallingAppEnforcingPermissions(appId);
    resolvedPackageName = resolveCallingPackageNameEnforcingSecurity(packageName);
    userState = getOrCreateUserStateLocked(resolvedUserId, false);
}
```

### 61.15.2 Custom Printer Icon Security

Custom printer icons from print services undergo user boundary validation
to prevent cross-user information leakage:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
private Icon validateIconUserBoundary(Icon icon, int resolvedCallingId) {
    if (icon != null && (icon.getType() == Icon.TYPE_URI
            || icon.getType() == Icon.TYPE_URI_ADAPTIVE_BITMAP)) {
        final int iconUserId = ContentProvider.getUserIdFromAuthority(
                icon.getUri().getAuthority(), resolvedCallingId);
        synchronized (mLock) {
            if (resolveCallingProfileParentLocked(iconUserId) != getCurrentUserId()) {
                return null; // Block cross-user icon access
            }
        }
    }
    return icon;
}
```

### 61.15.3 Print Services Query

The `READ_PRINT_SERVICES` permission is required to enumerate print services:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
public List<PrintServiceInfo> getPrintServices(int selectionFlags, int userId) {
    Preconditions.checkFlagsArgument(selectionFlags,
            PrintManager.DISABLED_SERVICES | PrintManager.ENABLED_SERVICES);
    mContext.enforceCallingOrSelfPermission(
            android.Manifest.permission.READ_PRINT_SERVICES, null);
```

---

## 61.16 Print Service Recommendations

Android provides a recommendation system for suggesting print services that
the user might want to install. `RemotePrintServiceRecommendationService`
handles the connection to recommendation services:

```java
// frameworks/base/services/print/java/com/android/server/print/
// RemotePrintServiceRecommendationService.java
```

Recommendations are displayed in the print UI when no installed print service
can communicate with a discovered printer.

---

## 61.17 AIDL Interfaces

The print framework defines several AIDL interfaces for cross-process
communication:

| Interface | Direction | Purpose |
|-----------|-----------|---------|
| `IPrintManager` | App -> System | Print job creation, query, cancel |
| `IPrintDocumentAdapter` | System -> App | Layout and write callbacks |
| `IPrintDocumentAdapterObserver` | System -> App | Adapter lifecycle notifications |
| `IPrintSpooler` | System -> Spooler | Job management in spooler |
| `IPrintSpoolerCallbacks` | Spooler -> System | Job state change callbacks |
| `IPrintSpoolerClient` | System -> Spooler | Client registration |
| `IPrintService` | System -> Service | Print service control |
| `IPrintServiceClient` | Service -> System | Printer and job updates |
| `IPrintJobStateChangeListener` | System -> App | Job state notifications |
| `IPrintServicesChangeListener` | System -> App | Service list notifications |
| `IPrinterDiscoveryObserver` | System -> App | Printer discovery events |
| `ILayoutResultCallback` | App -> System | Layout result delivery |
| `IWriteResultCallback` | App -> System | Write result delivery |

### 61.17.1 Listener Interfaces

The `PrintManager` client API exposes three listener interfaces:

```java
// frameworks/base/core/java/android/print/PrintManager.java

// Notified when any print job state changes
public interface PrintJobStateChangeListener {
    void onPrintJobStateChanged(PrintJobId printJobId);
}

// Notified when the set of print services changes
@SystemApi
public interface PrintServicesChangeListener {
    void onPrintServicesChanged();
}

// Notified when print service recommendations change
@SystemApi
public interface PrintServiceRecommendationsChangeListener {
    void onPrintServiceRecommendationsChanged();
}
```

State change listeners are wrapped in Binder-compatible wrappers and delivered
through the main looper handler:

```java
// frameworks/base/core/java/android/print/PrintManager.java
mHandler = new Handler(context.getMainLooper(), null, false) {
    @Override
    public void handleMessage(Message message) {
        switch (message.what) {
            case MSG_NOTIFY_PRINT_JOB_STATE_CHANGED: {
                SomeArgs args = (SomeArgs) message.obj;
                PrintJobStateChangeListenerWrapper wrapper =
                        (PrintJobStateChangeListenerWrapper) args.arg1;
                PrintJobStateChangeListener listener = wrapper.getListener();
                if (listener != null) {
                    PrintJobId printJobId = (PrintJobId) args.arg2;
                    listener.onPrintJobStateChanged(printJobId);
                }
                args.recycle();
            } break;
        }
    }
};
```

### 61.17.2 PrintManager Internal Extras

The `PrintManager` uses several hidden extras for communication with the
print dialog activity:

```java
// frameworks/base/core/java/android/print/PrintManager.java
public static final String ACTION_PRINT_DIALOG = "android.print.PRINT_DIALOG";
public static final String EXTRA_PRINT_DIALOG_INTENT =
        "android.print.intent.extra.EXTRA_PRINT_DIALOG_INTENT";
public static final String EXTRA_PRINT_JOB =
        "android.print.intent.extra.EXTRA_PRINT_JOB";
public static final String EXTRA_PRINT_DOCUMENT_ADAPTER =
        "android.print.intent.extra.EXTRA_PRINT_DOCUMENT_ADAPTER";
public static final int APP_ID_ANY = -2;
```

The `APP_ID_ANY` constant is used by `getGlobalPrintManagerForUser()` to create
a `PrintManager` instance that can access all print jobs regardless of app ID.

---

## 61.18 PrintFileDocumentAdapter

For the common case of printing an existing file, Android provides
`PrintFileDocumentAdapter`:

```java
// frameworks/base/core/java/android/print/PrintFileDocumentAdapter.java
```

This adapter handles reading from a `File` and writing to the print
spooler without the application needing to implement the full
`PrintDocumentAdapter` contract.

---

## 61.19 Threading Model

The print framework uses careful threading to avoid blocking the UI:

| Component | Thread | Purpose |
|-----------|--------|---------|
| `PrintManager` callbacks | Main thread | Deliver state changes to app |
| `PrintDocumentAdapter.onLayout()` | Main thread | App-driven layout |
| `PrintDocumentAdapter.onWrite()` | Main thread | App-driven rendering |
| `PrintManagerImpl` operations | Binder thread | Service request handling |
| `RemotePrintSpooler` calls | Background thread | Spooler IPC (may block) |
| `RemotePrintService` binding | Background thread | Service binding |
| `UserState` state management | Synchronized on `mLock` | Thread-safe state access |

The documentation explicitly warns:

> The calls [to RemotePrintSpooler] might be blocking and need the main
> thread to be unblocked to finish. Hence do not call this while holding
> any monitors that might need to be acquired on the main thread.

---

## 61.20 Security Model

The print framework enforces several security boundaries:

### 61.20.1 Permission Requirements

| Permission | Purpose |
|-----------|---------|
| `BIND_PRINT_SERVICE` | Only system can bind to print services |
| `INTERACT_ACROSS_USERS_FULL` | Cross-user print management |
| Feature: `FEATURE_PRINTING` | Device must support printing |

### 61.20.2 App Isolation

Applications can only see their own print jobs. The `PrintJobForAppCache`
in `UserState` maintains per-app caches:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
private final PrintJobForAppCache mPrintJobForAppCache = new PrintJobForAppCache();
```

### 61.20.3 Device Policy Integration

Enterprise management disables printing by setting the
`UserManager.DISALLOW_PRINTING` user restriction. `isPrintingEnabled()` checks
that restriction for the calling user; when it is set, `print()` and
`createPrintJob()` refuse to create a job, and `print()` surfaces the admin's
reason string via `DevicePolicyManagerInternal`:

```java
// frameworks/base/services/print/java/com/android/server/print/PrintManagerService.java
if (!isPrintingEnabled()) {
    DevicePolicyManagerInternal dpmi =
            LocalServices.getService(DevicePolicyManagerInternal.class);
    CharSequence disabledMessage = dpmi.getPrintingDisabledReasonForUser(callingUserId);
    if (disabledMessage != null) {
        Toast.makeText(mContext, Looper.getMainLooper(), disabledMessage,
                Toast.LENGTH_LONG).show();
    }
    // Drive the adapter through start()/finish() and return null.
}
```

---

## 61.21 Debugging Print Services

### 61.21.1 Shell Commands

The `PrintShellCommand` class implements two `cmd print` subcommands, both of
which control whether the system may bind to print services published by instant
apps:

```bash
# Read the instant-app binding policy for a user (default: USER_SYSTEM)
$ adb shell cmd print get-bind-instant-service-allowed [--user <USER_ID>]

# Set the instant-app binding policy
$ adb shell cmd print set-bind-instant-service-allowed [--user <USER_ID>] true|false
```

The richest view of live print state comes from `dumpsys`, which prints every
`UserState`'s installed services, active services, spooler binding, and cached
print jobs:

```bash
# Dump print manager state (text)
$ adb shell dumpsys print

# Dump as protobuf for structured analysis
$ adb shell dumpsys print --proto
```

The `dumpsys print` handler in `PrintManagerService` (Section 61.7) snapshots
the per-user `UserState` list under `mLock`, then renders it through a
`DualDumpOutputStream` that targets either an `IndentingPrintWriter` (text) or a
`ProtoOutputStream` (`--proto`).

### 61.21.2 Logging

Enable verbose logging for print components:

```bash
$ adb shell setprop log.tag.PrintManager VERBOSE
$ adb shell setprop log.tag.PrintManagerService VERBOSE
$ adb shell setprop log.tag.RemotePrintSpooler VERBOSE
$ adb shell setprop log.tag.RemotePrintService VERBOSE
$ adb shell setprop log.tag.UserState VERBOSE
```

### 61.21.3 Proto Dump

The print framework supports protobuf-based dumps for structured analysis:

```java
// frameworks/base/services/print/java/com/android/server/print/UserState.java
// Uses PrintUserStateProto, CachedPrintJobProto, InstalledPrintServiceProto,
// PrinterDiscoverySessionProto for structured dumps
```

---

## 61.22 Key Constants Reference

| Constant | Value | Location |
|----------|-------|----------|
| `PRINT_SPOOLER_PACKAGE_NAME` | `com.android.printspooler` | `PrintManager.java` |
| `BIND_SPOOLER_SERVICE_TIMEOUT` | 10,000ms (eng: 120,000ms) | `RemotePrintSpooler.java` |
| `SERVICE_RESTART_DELAY_MILLIS` | 500ms | `UserState.java` |
| `MILS_PER_INCH` | 1000 | `PrintedPdfDocument.java` |
| `POINTS_IN_INCH` | 72 | `PrintedPdfDocument.java` |
| `COMPONENT_NAME_SEPARATOR` | `:` | `UserState.java` |
| `BACKGROUND_USER_ID` | -10 | `PrintManagerImpl` |
| Service action | `android.printservice.PrintService` | `PrintService.java` |
| Meta-data key | `android.printservice` | `PrintService.java` |

---

## 61.23 Printer Setup Activity (Android 17)

Android 17 lets a print service publish a *setup* activity for a printer, in
addition to the long-standing *info* activity. The motivating case is a printer
that a service can discover but cannot print to until the user finishes a
one-time setup step (for example, claiming the printer, entering credentials, or
installing a vendor profile). The feature is guarded by the
`android.print.flags.enable_setup_activity` aconfig flag:

```text
# frameworks/base/core/java/android/print/flags/flags.aconfig
flag {
    name: "enable_setup_activity"
    namespace: "printing"
    description: "Enable PrintService implementations to provide a printer setup activity"
    is_exported: true
}
```

### 61.23.1 The setup intent on PrinterInfo

`PrinterInfo` gains a nullable `mSetupIntent` (`PendingIntent`) alongside the
existing `mInfoIntent`. A print service attaches it from
`PrinterInfo.Builder.setSetupIntent()`:

```java
// frameworks/base/core/java/android/print/PrinterInfo.java
@FlaggedApi(Flags.FLAG_ENABLE_SETUP_ACTIVITY)
public @NonNull Builder setSetupIntent(@NonNull PendingIntent setupIntent) {
    mSetupIntent = Objects.requireNonNull(setupIntent);
    return this;
}
```

Every field touchpoint -- the constructor, parceling, `hashCode()`, `equals()`,
and `toString()` -- is wrapped in `if (Flags.enableSetupActivity())`, so the
extra `PendingIntent` is read from and written to the parcel only when the flag
is on. This keeps the wire format compatible with services compiled against the
flag-off build. The accessor `getSetupIntent()` is deliberately marked `@hide`:
only the framework's own print UI is meant to launch the setup screen, so a
third-party app that obtains a `PrinterInfo` through other APIs cannot start it.

### 61.23.2 How the spooler blocks printing until setup completes

The print dialog (`PrintActivity` in the spooler) treats a printer with a setup
intent as not-yet-printable. `needsSetup()` returns true only when the flag is
on and the selected printer carries a setup intent:

```java
// frameworks/base/packages/PrintSpooler/src/com/android/printspooler/ui/PrintActivity.java
private static boolean needsSetup(PrinterInfo printer) {
    return android.print.flags.Flags.enableSetupActivity()
            && printer != null
            && printer.getSetupIntent() != null;
}
```

When the user tries to print, `setupAndPrint()` first checks `needsSetup()`. If
setup is required it launches the service's setup `PendingIntent` for a result
(rather than confirming the print job), allowing the activity to launch from the
spooler via `MODE_BACKGROUND_ACTIVITY_START_ALLOWED`. Only when setup is not
required (or has completed) does the spooler fall through to `confirmPrint()`:

```mermaid
flowchart TB
    PRESS["User presses Print"]
    NEEDS{"needsSetup printer<br/>(flag on AND<br/>setupIntent != null)?"}
    LAUNCH["startIntentSenderForResult<br/>(printer setup activity)"]
    DONE{"Setup result OK?"}
    CONFIRM["confirmPrint<br/>(spool job, STATE_QUEUED)"]
    STAY["Stay on print dialog"]

    PRESS --> NEEDS
    NEEDS -->|"No"| CONFIRM
    NEEDS -->|"Yes"| LAUNCH
    LAUNCH --> DONE
    DONE -->|"Yes"| CONFIRM
    DONE -->|"No"| STAY
```

The setup activity may also return an alternate printer, in case the user picks
a different one during setup.

---

## 61.24 Print Telemetry (Android 17)

Android 17 adds structured statsd metrics to the print spooler so the platform
can measure print outcomes, discovery, and UI engagement. All logging is gated
by the `com.android.printspooler.flags.printing_telemetry` flag:

```text
# frameworks/base/packages/PrintSpooler/flags/flags.aconfig
flag {
  name: "printing_telemetry"
  namespace: "printing"
  description: "Metrics tracking final print job status, printer discovery, printer capabilities, and major UI actions."
}
```

### 61.24.1 The statsd atoms

The atoms live in a dedicated extension file and are emitted by the
`printspooler` module:

```text
# frameworks/proto_logging/stats/atoms/printing/printing_extension_atoms.proto
FrameworkPrintJob              (1071) - final job state + attributes
FrameworkPrinterDiscovery      (1072) - discovered printer + capabilities
FrameworkMainPrintUiLaunched   (1073) - print dialog opened
FrameworkAdvancedOptionsUiLaunched (1074) - advanced options opened
```

`FrameworkPrintJob` carries the terminal state (completed / failed / canceled),
color mode, media size, horizontal/vertical DPI, orientation, duplex mode,
document type, whether the output was saved to PDF, page count, and the print
service UID. `FrameworkPrinterDiscovery` records the discovering service UID and
the printer's supported color modes, media sizes, and duplex modes. Two
additional `Bips*` atoms (1075-1078) come from the built-in print service
(`builtinprintservice`) rather than the spooler.

### 61.24.2 Where the events are logged

`PrintSpoolerService.logPrintJobFinalState()` emits a `FrameworkPrintJob` when a
job reaches a final spooler state. It resolves the print service's UID, reads
the optional attributes (`PrintAttributes`) and document info
(`PrintDocumentInfo`), and hands them to an asynchronous logger:

```java
// frameworks/base/packages/PrintSpooler/src/com/android/printspooler/model/PrintSpoolerService.java
private void logPrintJobFinalState(PrinterId printerId, PrintJobInfo printJob) {
    if (!Flags.printingTelemetry()) {
        return;
    }
    // ... resolve serviceUId, read PrintAttributes + PrintDocumentInfo ...
    StatsAsyncLogger.INSTANCE.PrintJob(serviceUId, state, colorMode, size,
            resolution, duplexMode, docType, savedPdf, pageCount);
}
```

The proto comments name the exact source files for each atom: `FrameworkPrintJob`
is logged from `PrintSpoolerService.java`, `FrameworkPrinterDiscovery` from
`PrinterDiscoverySession.java`, and the two UI-launch atoms from `PrintActivity.java`.
To support these atoms, Android 17 added small accessors used by the logger,
including media-size and document-type lookups read from `PrintAttributes` and
`PrintDocumentInfo`.

---

## 61.25 The Spooler Is No Longer Preinstalled Everywhere (Android 17)

Earlier releases assumed `com.android.printspooler` was present on every user.
Android 17 narrows the preinstall allowlist: the spooler is installed only for
user types that need it.

```xml
<!-- build/make/target/product/sysconfig/preinstalled-packages-platform-handheld-system.xml -->
<install-in-user-type package="com.android.printspooler">
    <install-in user-type="FULL" />
    <install-in user-type="android.os.usertype.profile.CLONE" />
</install-in-user-type>
```

Because the spooler can now be absent on a given user, code that talks to it
must tolerate that. The `dumpsys print` path is the visible example: a stale
implementation called into `RemotePrintSpooler.dump()` for every user state,
which failed when the spooler package was not installed. Android 17 adds an
install check that short-circuits the dump:

```java
// frameworks/base/services/print/java/com/android/server/print/RemotePrintSpooler.java
public void dump(@NonNull DualDumpOutputStream dumpStream) {
    synchronized (mLock) {
        if (!isInstalled()) {
            return;
        }
        // ... write is_destroyed / is_bound ...
    }
}

private boolean isInstalled() {
    try {
        mContext.createPackageContextAsUser(PRINT_SPOOLER_PACKAGE_NAME, 0, mUserHandle);
        return true;
    } catch (PackageManager.NameNotFoundException e) {
        return false;
    } catch (Exception e) {
        Slog.e(LOG_TAG, "Failed to check if print spooler is installed", e);
        return false;
    }
}
```

`isInstalled()` probes for the spooler package on the proxy's own
`mUserHandle` via `createPackageContextAsUser()`. When it returns false the dump
is skipped for that user, so `adb shell dumpsys print` succeeds on devices where
some users have no spooler.

---

## Try It

Use a device or emulator running Android 17 to observe the print framework in
action.

1. **Inspect live print state.** Open any app with print support (Chrome, Files,
   Photos), start a print, then dump the framework state:

   ```bash
   adb shell dumpsys print
   adb shell dumpsys print --proto > print_state.pb
   ```

   Note the per-user `UserState` sections, the installed and active print
   services, and any cached print jobs. On a device with secondary users, confirm
   the command no longer fails even though the spooler may be absent on some users
   (Section 61.25).

2. **Watch the disabled-services model.** List the print services, then toggle
   one in Settings and re-read the secure setting that actually persists the
   choice:

   ```bash
   adb shell settings get secure disabled_print_services
   ```

   Disable a service in Settings and observe the `ComponentName` appear in the
   colon-separated list; the *enabled* setting stays empty (Section 61.8.2).

3. **Trace a print job's lifecycle.** Enable verbose logging and follow a job
   from `STATE_CREATED` through `STATE_QUEUED` to a terminal state:

   ```bash
   adb shell setprop log.tag.PrintManager VERBOSE
   adb shell setprop log.tag.RemotePrintSpooler VERBOSE
   adb logcat | grep -i print
   ```

4. **Toggle the new flags.** Inspect the Android 17 print flags and their state:

   ```bash
   adb shell device_config get printing enable_setup_activity
   adb shell device_config get printing printing_telemetry
   ```

   With `printing_telemetry` on, complete a print and confirm a `FrameworkPrintJob`
   atom is logged (Section 61.24).

5. **Implement a minimal print service.** Build a `PrintService` subclass that
   reports a single fake printer in `onCreatePrinterDiscoverySession()` and
   completes jobs in `onPrintJobQueued()`. Attach a setup intent with
   `PrinterInfo.Builder.setSetupIntent()` and watch the print dialog block on
   setup before allowing the job (Section 61.23).

---

## Summary

Android's printing framework is a well-structured system built on four layers:
the client API (`PrintManager`), the system service (`PrintManagerService` with
per-user `UserState`), the print spooler process (`com.android.printspooler`),
and pluggable print services (`PrintService`).

The `PrintDocumentAdapter` contract between applications and the print framework
ensures content can be re-laid-out for different print attributes, with the
framework always requesting PDF output. The seven-state print job lifecycle
(`CREATED` -> `QUEUED` -> `STARTED` -> `COMPLETED`/`FAILED`/`CANCELED`, with
`BLOCKED` as an intermediate state) provides fine-grained tracking of print
progress.

Printer discovery is handled through `PrinterDiscoverySession`, which supports
lazy capability loading and real-time printer state tracking. The session-based
design ensures that print services only perform expensive network discovery
when the system needs it.

The spooler and print service proxies (`RemotePrintSpooler` and
`RemotePrintService`) handle the complexities of cross-process communication,
including binding lifecycle, timeouts, crash recovery, and deferred command
queuing. The multi-user architecture ensures complete isolation between
users while sharing the underlying framework infrastructure.

Android 17 refines several of these layers. Print services can now publish a
per-printer setup activity (`enable_setup_activity`), which the spooler launches
to block printing until the user finishes setup. A new telemetry layer
(`printing_telemetry`) emits structured statsd atoms for job outcomes, printer
discovery, and print-dialog engagement. The persisted service state continues to
track the *disabled* set in `Settings.Secure.DISABLED_PRINT_SERVICES`, with the
legacy enabled-list setting surviving only as a one-time migration input.
Because the spooler is no longer preinstalled on every user, framework code such
as `dumpsys print` now guards spooler access with an install check, and
`PrintManager.print()` returns `null` instead of leaking
`ActivityNotFoundException` when the dialog activity cannot be resolved.
