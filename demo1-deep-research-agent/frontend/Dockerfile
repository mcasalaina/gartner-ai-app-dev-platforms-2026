FROM node:22-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
