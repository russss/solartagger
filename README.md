# Solartagger

This is the app code for [https://solartagger.russss.dev](https://solartagger.russss.dev)

## Development

This code requires the [openinframap](https://openinframap.org) database so it's not going to be especially easy to develop, unfortunately.

	poetry install
	poetry run uvicorn --reload main:app
