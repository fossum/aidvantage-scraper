FROM python:3.12

# Set up ChromeDriver
RUN apt update && \
    apt install -y chromium chromium-driver pipenv unzip && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m ensurepip --upgrade && \
    python3 -m pip install --upgrade setuptools pipenv

# Install dependencies
COPY . /app
WORKDIR /app
RUN python3 -m pipenv lock
RUN pipenv requirements > requirements.txt
RUN pip install -r requirements.txt

# Run the tests
CMD ["python", "temp1.py"]
