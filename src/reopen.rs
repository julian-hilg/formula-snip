//! "Open the app again" shows the panel of the already-running instance.
//!
//! * All OSes: a second `formula-snip` process pokes the first over a local socket and exits.
//! * macOS: opening the app from Finder/Spotlight/Launchpad while it runs doesn't start a
//!   second process; macOS sends a "reopen" Apple Event instead, which we handle here.
//!   Useful when the menu-bar icon is hidden (e.g. behind the MacBook notch).

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::OnceLock;
use std::time::Duration;

const ADDR: &str = "127.0.0.1:47613";
const HELLO: &[u8] = b"formula-snip:show";

/// If another instance is running, ask it to show its panel and return true (caller exits).
pub fn signal_running_instance() -> bool {
    let addr: SocketAddr = ADDR.parse().unwrap();
    match TcpStream::connect_timeout(&addr, Duration::from_millis(300)) {
        Ok(mut s) => s.write_all(HELLO).is_ok(),
        Err(_) => false,
    }
}

/// Listen for other instances (and on macOS for the reopen event) and call `show`.
pub fn listen(show: impl Fn() + Send + Sync + Clone + 'static) {
    if let Ok(listener) = TcpListener::bind(ADDR) {
        let show = show.clone();
        std::thread::spawn(move || {
            for mut stream in listener.incoming().flatten() {
                let mut buf = [0u8; 32];
                let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
                let n = stream.read(&mut buf).unwrap_or(0);
                if &buf[..n] == HELLO {
                    show();
                }
            }
        });
    }
    #[cfg(target_os = "macos")]
    mac::install(show);
}

static SHOW: OnceLock<Box<dyn Fn() + Send + Sync>> = OnceLock::new();

#[cfg(target_os = "macos")]
mod mac {
    use super::SHOW;
    use objc2::rc::Retained;
    use objc2::runtime::NSObject;
    use objc2::{define_class, msg_send, sel, AllocAnyThread};
    use objc2_foundation::{NSAppleEventDescriptor, NSAppleEventManager};

    define_class!(
        #[unsafe(super(NSObject))]
        #[name = "FormulaSnipReopenHandler"]
        struct ReopenHandler;

        impl ReopenHandler {
            #[unsafe(method(handleReopen:withReply:))]
            fn handle_reopen(&self, _event: &NSAppleEventDescriptor, _reply: &NSAppleEventDescriptor) {
                if let Some(show) = SHOW.get() {
                    show();
                }
            }
        }
    );

    /// Must run after the app finished launching (AppKit installs its own handler then).
    pub fn install(show: impl Fn() + Send + Sync + 'static) {
        let _ = SHOW.set(Box::new(show));
        let handler: Retained<ReopenHandler> = unsafe { msg_send![ReopenHandler::alloc(), init] };
        const CORE_EVENT_CLASS: u32 = u32::from_be_bytes(*b"aevt");
        const REOPEN_APPLICATION: u32 = u32::from_be_bytes(*b"rapp");
        let manager = NSAppleEventManager::sharedAppleEventManager();
        unsafe {
            let _: () = msg_send![&*manager, setEventHandler: &*handler,
                andSelector: sel!(handleReopen:withReply:),
                forEventClass: CORE_EVENT_CLASS, andEventID: REOPEN_APPLICATION];
        }
        std::mem::forget(handler); // the event manager doesn't retain it
    }
}
