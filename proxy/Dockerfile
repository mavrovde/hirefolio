FROM nginx:1.26-alpine

RUN --mount=type=cache,target=/var/cache/apk \
    apk add openssl curl

COPY default.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
COPY certs /etc/nginx/ssl
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
