import { defineStore } from "pinia";
import { ref } from "vue";
import type { Finding } from "../types/models";

export const useFindingsStore = defineStore("findings", () => {
  const items = ref<Finding[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  function replaceAll(findings: Finding[]): void {
    items.value = findings;
  }

  return { items, loading, error, replaceAll };
});
