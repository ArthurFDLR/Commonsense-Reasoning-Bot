# run
run:
	poetry run python .\commonsense_reasoning_bot

# formatting

fmt-black:
	poetry run black commonsense_reasoning_bot/Simulator.py

# lint

lint-black:
	poetry run black --check commonsense_reasoning_bot/

lint: lint-black