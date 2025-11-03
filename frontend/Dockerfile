# syntax=docker/dockerfile:1

FROM node:20-alpine AS deps

WORKDIR /usr/src/app

COPY my-react-app/package*.json ./

RUN npm ci

FROM node:20-alpine

WORKDIR /usr/src/app

ENV HOST=0.0.0.0 \
    PORT=5173

COPY --from=deps /usr/src/app/node_modules ./node_modules
COPY my-react-app/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]