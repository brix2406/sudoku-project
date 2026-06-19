FROM nginx:alpine

RUN apk add --no-cache openssl goaccess

COPY default.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /etc/nginx/ssl /var/log/nginx/goaccess

ENTRYPOINT ["/entrypoint.sh"]
