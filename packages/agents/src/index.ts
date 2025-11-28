export function createAgent(name: string) {
  return {
    name,
    run: () => console.log(`Agent ${name} running`),
  };
}
