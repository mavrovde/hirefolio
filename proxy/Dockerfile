FROM nginx:latest

RUN apt-get update && apt-get install -y openssl curl && rm -rf /var/lib/apt/lists/*
RUN sed -i 's/worker_processes  1;/worker_processes  1;\n    aio off;/g' /etc/nginx/nginx.conf || true
RUN find /etc/nginx -type f -exec sed -i 's/aio threads;/aio off;/g' {} + || true

COPY default.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
COPY certs /etc/nginx/ssl
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
