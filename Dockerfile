FROM cae-artifactory.jpl.nasa.gov:17001/redhat/ubi8:8.7

RUN groupadd -r bifrost --gid=2001  && \
    useradd -r -g bifrost --uid=2001 --home-dir=/home/bifrost --shell=/bin/bash bifrost && \
    mkdir -p /home/bifrost && \
    chown -R bifrost:bifrost /home/bifrost

COPY mariadb.repo /etc/yum.repos.d/mariadb.repo

RUN dnf update -y && \
    dnf install -y \
        java-11-openjdk-headless.x86_64 \
        openssl \
        openssh \
        curl \
        wget \
        hostname \
        git \
        graphviz \
        make \
        gcc \
        openssl-devel \
        bzip2-devel \
        libffi-devel \
        zlib-devel \
        sqlite-devel \
        policycoreutils-python-utils \
        MariaDB-client && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Install Python 3.8.12
WORKDIR /opt
RUN wget https://www.python.org/ftp/python/3.8.12/Python-3.8.12.tgz && \
    tar xzf Python-3.8.12.tgz && \
    rm -rf Python-3.8.12.tgz

WORKDIR /opt/Python-3.8.12
RUN ./configure --enable-optimizations --enable-loadable-sqlite-extensions > /dev/null
RUN make altinstall > /dev/null

# Install KMC client
RUN rpm -Uvh https://ammos:g3tpackag3s@asis-repo1.jpl.nasa.gov/asis/rhel8/x86_64/RPMS/MGSS-asis-repo-release-jplnet-latest.el8.noarch.rpm
RUN dnf -y install MGSS-ammos-system-current-A32.0.sunrisekmcclient.2

# Rename AMMOS KMC default group 'users' to 'cmdenc' and add 'bifrost' user
RUN groupmod --new-name cmdenc users && \ 
    usermod -a -G cmdenc bifrost && \
    chgrp -R cmdenc /var/ammos/kmc-crypto-client/logs && \
    chgrp -h cmdenc /usr/lib64/libcrypto.so.1.1

# Create virtualenv
ENV VIRTUAL_ENV=/opt/venv
RUN /usr/local/bin/python3.8 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . /app
WORKDIR /app

# Create sunrise directory
RUN mkdir /sunrise && \
    chown -R bifrost:bifrost /app /sunrise $VIRTUAL_ENV

# Install Bifrost
RUN pip3 install -r requirements.txt
RUN pip3 install -e . # might be fixed with empty init or wheel or zip_ok=False

USER bifrost

ENV AIT_CONFIG=/app/config/config_docker.yaml
ENV AIT_ROOT="$VIRTUAL_ENV/lib/python3.8/site-packages/ait"
ENV BIFROST_SERVICES_CONFIG=/app/config/services_docker.yaml
ENV PYTHONPATH=/ammos/kmc-crypto-client/lib/python3.8/site-packages
ENV LD_PRELOAD=/usr/lib64/libcrypto.so.1.1
ENV PYTHONUNBUFFERED=1

# Bifrost Webserver
EXPOSE 8000

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["bifrost"]
