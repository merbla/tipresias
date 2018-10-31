# Use an official Python runtime as a parent image
FROM python:3

# Install R to use rpy2 for access to R packages
RUN apt-get update && apt-get -y install r-base

RUN apt-get update && apt-get -y install curl
RUN curl -sL https://deb.nodesource.com/setup_8.x | bash \ 
  && apt-get install nodejs

# Install dependencies
COPY requirements.txt /app/
WORKDIR /app/

RUN pip3 install --trusted-host pypi.python.org -r requirements.txt

COPY requirements.r /app/
RUN Rscript requirements.r

# Install dependencies
COPY package.json yarn.lock /app/
RUN yarn

# Since backend serves the assets in production, it depends on build/ in development as well,
# so we need to make sure build/index.html exists in all environments
RUN yarn build

# Add the rest of the code
COPY . /app/

# Make port 8000 available for the app
EXPOSE 8000

# CMD craft serve
CMD python3 manage.py runserver
