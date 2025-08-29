import curses
import locale
import sys

class Console:
    def __init__(self):
        # Устанавливаем локаль для корректной обработки Unicode
        locale.setlocale(locale.LC_ALL, '')
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.current_row = 0
        self.max_rows, self.max_cols = self.stdscr.getmaxyx()
        self.input_buffer = ""
        self.input_prompt = ""
        self.cursor_pos = 0  # Позиция курсора в буфере

    def print(self, text):
        if self.current_row < self.max_rows - 1:
            # Преобразуем текст в строку и обрезаем до ширины экрана
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
        # Выводим приглашение для ввода
        try:
            self.stdscr.addstr(self.max_rows-1, 0, prompt[:self.max_cols-1])
        except curses.error:
            pass
        self.stdscr.refresh()
        curses.echo()

        col = len(prompt)  # Текущая позиция курсора на экране
        while True:
            try:
                self.stdscr.move(self.max_rows-1, col)  # Перемещаем курсор на экране
                char = self.stdscr.get_wch()  # Используем get_wch для Unicode
                if char == '\n' or char == '\r':  # Обработка Enter
                    break
                elif char in (curses.KEY_BACKSPACE, 127, '\b'):  # Обработка Backspace
                    if self.cursor_pos > 0:
                        # Удаляем символ перед курсором
                        self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                        self.cursor_pos -= 1
                        col = max(len(prompt), col - 1)
                        # Перерисовываем строку ввода
                        self.stdscr.addstr(self.max_rows-1, len(prompt), self.input_buffer + " ")
                        self.stdscr.move(self.max_rows-1, col)
                elif char == curses.KEY_LEFT:  # Обработка стрелки влево
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                        col = max(len(prompt), col - 1)
                        self.stdscr.move(self.max_rows-1, col)
                elif char == curses.KEY_RIGHT:  # Обработка стрелки вправо
                    if self.cursor_pos < len(self.input_buffer):
                        self.cursor_pos += 1
                        col = min(self.max_cols - 1, col + 1)
                        self.stdscr.move(self.max_rows-1, col)
                else:  # Обработка печатных символов
                    if isinstance(char, str):
                        # Вставляем символ в позицию курсора
                        self.input_buffer = self.input_buffer[:self.cursor_pos] + char + self.input_buffer[self.cursor_pos:]
                        self.cursor_pos += 1
                        try:
                            # Перерисовываем строку ввода
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
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()