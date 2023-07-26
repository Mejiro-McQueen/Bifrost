from node:19 AS builder
RUN git clone https://github.com/nasa/openmct.git
WORKDIR openmct
RUN	git checkout tags/v2.2.5
RUN npm update && npm install

from nginx:latest
COPY nginx.conf /etc/nginx/nginx.conf

WORKDIR /app/dist
COPY --from=builder /openmct/dist ./
COPY ./index.html ./
COPY ./bifrost.js ../
COPY ./bifrost-config.json ../

ENV NGINX_HOST=localhost
ENV NGINX_PORT=8081
EXPOSE 8081:8081
