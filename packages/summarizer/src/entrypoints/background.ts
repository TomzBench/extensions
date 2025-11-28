import { createAgent } from "@extensions/agents";

export default defineBackground(() => {
  const agent = createAgent("summarizer");
  agent.run();
});
