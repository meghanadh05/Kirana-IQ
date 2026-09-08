FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# VITE_* values are inlined at build time, so the API URL is baked in here.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

EXPOSE 5173

CMD ["npm", "run", "preview"]
