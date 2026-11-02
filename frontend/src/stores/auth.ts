import { defineStore } from "pinia";
import { ref } from "vue";

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref<string | null>(null);
  const isAuthenticated = ref(false);

  function setSession(token: string): void {
    accessToken.value = token;
    isAuthenticated.value = true;
  }

  function clearSession(): void {
    accessToken.value = null;
    isAuthenticated.value = false;
  }

  return { accessToken, isAuthenticated, setSession, clearSession };
});
