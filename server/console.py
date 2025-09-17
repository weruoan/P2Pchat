import sys
import locale
import platform

# Check for Windows and import appropriate curses module
if platform.system() == "Windows":
    try:
        import curses
    except ImportError:
        raise ImportError("The 'windows-curses' package is required on Windows. Install it using: pip install windows-curses")
else:
    import curses

class Console:
    def __init__(self):
        # Set locale for proper Unicode handling
        if platform.system() == "Windows":
            # Windows-specific encoding to support Unicode
            locale.setlocale(locale.LC_ALL, '.utf8')
        else:
            locale.setlocale(locale.LC_ALL, '')

        # Initialize curses
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.current_row = 0
        self.max_rows, self.max_cols = self.stdscr.getmaxyx()
        self.input_buffer = ""
        self.input_prompt = ""
        self.cursor_pos = 0  # Cursor position in buffer

        # Ensure proper encoding for Windows console
        if platform.system() == "Windows":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # Set console to UTF-8
            except Exception:
                pass

    def print(self, text):
        if self.current_row < self.max_rows - 1:
            # Convert text to string and truncate to screen width
            text = str(text)[:self.max_cols-1]
            try:
                self.stdscr.addstr(self.current_row, 0, text)
            except curses.error:
                pass
            self.current_row += 1
            self.stdscr.refresh()

    def input(self, prompt=""):
        if self.input_prompt:
            prompt = self.input_prompt
        self.input_buffer = ""
        self.cursor_pos = 0
        # Display input prompt
        try:
            self.stdscr.addstr(self.max_rows-1, 0, prompt[:self.max_cols-1])
        except curses.error:
            pass
        self.stdscr.refresh()
        curses.echo()

        col = len(prompt)  # Current cursor position on screen
        while True:
            try:
                self.stdscr.move(self.max_rows-1, col)  # Move cursor on screen
                char = self.stdscr.get_wch()  # Use get_wch for Unicode
                if char in ('\n', '\r'):  # Handle Enter
                    break
                elif char in (curses.KEY_BACKSPACE, 127, '\b'):  # Handle Backspace
                    if self.cursor_pos > 0:
                        # Remove character before cursor
                        self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                        self.cursor_pos -= 1
                        col = max(len(prompt), col - 1)
                        # Redraw input line
                        self.stdscr.addstr(self.max_rows-1, len(prompt), self.input_buffer + " ")
                        self.stdscr.move(self.max_rows-1, col)
                elif char == curses.KEY_LEFT:  # Handle left arrow
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                        col = max(len(prompt), col - 1)
                        self.stdscr.move(self.max_rows-1, col)
                elif char == curses.KEY_RIGHT:  # Handle right arrow
                    if self.cursor_pos < len(self.input_buffer):
                        self.cursor_pos += 1
                        col = min(self.max_cols - 1, col + 1)
                        self.stdscr.move(self.max_rows-1, col)
                else:  # Handle printable characters
                    if isinstance(char, str):
                        # Insert character at cursor position
                        self.input_buffer = self.input_buffer[:self.cursor_pos] + char + self.input_buffer[self.cursor_pos:]
                        self.cursor_pos += 1
                        try:
                            # Redraw input line
                            self.stdscr.addstr(self.max_rows-1, len(prompt), self.input_buffer + " ")
                            col = min(self.max_cols - 1, col + 1)
                        except curses.error:
                            pass
                self.stdscr.refresh()
            except curses.error:
                pass

        curses.noecho()
        result = self.input_buffer
        self.input_buffer = ""
        self.cursor_pos = 0
        self.stdscr.move(self.max_rows-1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        return result

    def clear(self):
        self.stdscr.clear()
        self.current_row = 0
        self.stdscr.refresh()

    def __del__(self):
        try:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()
        except:
            pass