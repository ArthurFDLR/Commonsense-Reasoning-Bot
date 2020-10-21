# run
run:
	python38 -m poetry run python .\commonsense_reasoning_bot

# formatting

fmt-black:
	python38 -m poetry run black commonsense_reasoning_bot/

# lint

lint-black:
	python38 -m poetry run black --check commonsense_reasoning_bot/

lint: lint-black