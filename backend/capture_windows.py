"""Select a screen rectangle without the Windows Snipping Tool or clipboard."""
import ctypes
import sys


def selection_box(start, end, size):
    """Normalize either drag direction and clamp to screenshot pixel bounds."""
    width, height = size
    x1, x2 = sorted((max(0, min(width, start[0])), max(0, min(width, end[0]))))
    y1, y2 = sorted((max(0, min(height, start[1])), max(0, min(height, end[1]))))
    return (x1, y1, x2, y2) if x2 - x1 >= 3 and y2 - y1 >= 3 else None


def main():
    # Keep screenshot pixels, Tk coordinates and mixed-DPI monitor bounds aligned.
    user32 = ctypes.windll.user32
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import tkinter as tk
    from PIL import ImageEnhance, ImageGrab, ImageTk

    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    screenshot = ImageGrab.grab(all_screens=True)
    width, height = screenshot.size
    root = tk.Tk()
    root.title("Formula Snip - Select area (Esc to cancel)")
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.geometry(f"{width}x{height}+0+0")
    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    dimmed = ImageTk.PhotoImage(ImageEnhance.Brightness(screenshot).enhance(0.55))
    canvas.create_image(0, 0, anchor="nw", image=dimmed)
    canvas.create_text(width // 2, 32, text="Drag to select a formula  |  Esc: cancel", fill="white", font=("Segoe UI", 16))
    selection = canvas.create_rectangle(0, 0, 0, 0, outline="#5cb5ff", width=2, state="hidden")
    origin = None
    failure = []

    def press(event):
        nonlocal origin
        origin = (event.x, event.y)
        canvas.itemconfigure(selection, state="normal")
        canvas.coords(selection, event.x, event.y, event.x, event.y)

    def drag(event):
        if origin is not None:
            canvas.coords(selection, *origin, event.x, event.y)

    def release(event):
        if origin is None:
            return
        box = selection_box(origin, (event.x, event.y), screenshot.size)
        if box is None:
            return
        try:
            screenshot.crop(box).save(sys.argv[1])
        except Exception as exc:
            failure.append(exc)
        root.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    root.bind("<Escape>", lambda _: root.destroy())
    root.bind("<Button-3>", lambda _: root.destroy())
    root.update_idletasks()
    # Geometry's negative coordinates mean 'from right/bottom'; position through
    # Win32 instead so monitors to the left/above the primary are supported.
    user32.GetParent.argtypes = [ctypes.c_void_p]
    user32.GetParent.restype = ctypes.c_void_p
    hwnd = user32.GetParent(root.winfo_id())
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos(hwnd, ctypes.c_void_p(-1), left, top, width, height, 0x0040)
    root.lift()
    root.focus_force()
    root.mainloop()
    if failure:
        raise failure[0]


if __name__ == "__main__":
    main()
