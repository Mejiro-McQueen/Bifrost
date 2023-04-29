# TODO: Remove gevent, Upgrade to python 3.10, Move to Alpine
FROM python:3.8 

# Set venv
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set users, groups, directories 
RUN useradd -ms /bin/bash -u 2001 bifrost
RUN mkdir /gds /app && chown -R bifrost /app /gds $VIRTUAL_ENV

USER bifrost

# Install Bifrost Dependencies
COPY --chown=bifrost requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Install Bifrost
WORKDIR /app
COPY --chown=bifrost . ./bifrost
RUN pip install ./bifrost

# Setup Default Variables
# Tip: You can override using your own dockerfile.
# Tip: You can override using the docker-compose config template.
ENV AIT_CONFIG=/app/config/config.yaml
ENV AIT_ROOT=/app/ait
ENV BIFROST_SERVICES_CONFIG=/app/config/services.yaml
ENV PYTHONUNBUFFERED=1

# Bifrost
EXPOSE 80
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["bifrost"]
