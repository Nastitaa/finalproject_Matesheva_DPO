#!/usr/bin/env python3
"""Точка входа в приложение."""

from valutatrade_hub.cli.interface import CLI


def main():
    cli = CLI()
    cli.run()


if __name__ == "__main__":
    main()
