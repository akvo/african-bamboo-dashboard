import nextJest from "next/jest.js";

const createJestConfig = nextJest({
  dir: "./",
});

/** @type {import('jest').Config} */
const config = {
  testEnvironment: "jsdom",
  transformIgnorePatterns: ["/node_modules/(?!jose)"],
};

export default createJestConfig(config);
