"""Entry point for the SIMPEG Jurnal Harian Otomatis application."""
from ui import JournalApp


def main() -> None:
    app = JournalApp()
    app.mainloop()


if __name__ == "__main__":
    main()
