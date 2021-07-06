install: setup.py
	python setup.py install

build: setup.py $(shell find harvest)
	python setup.py build

test: $(shell find harvest)
	coverage run --source harvest -m unittest discover -s test
	coverage report
	coverage html

clean:
	rm -rf build dist harvest.egg-info \
		.coverage htmlcov