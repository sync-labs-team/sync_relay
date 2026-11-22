// tokens: context of the main session's last call; piso: lowest context seen since the start or /clear (the baseline); adiado: tokens when the user clicked "Later" (or Cancel);
// fase: aguardando (live agent), escrevendo while the model writes the handoff, contando (the 15 s notice of auto mode), pronta (handoff saved, /clear refused: the user types /clear);
// apresentado: the one-time first-install intro was already seen; auto: automatic mode on (default off); interativo: a person is at the prompt; restante: seconds left in the countdown; limiar: D of the switch rule (tokens above the baseline, capped at 80% of the way to compaction; config threshold_tokens); compact: the CLI's auto-compaction point (c) and where it came from (origem);
// carregado: this session's state was already read from the store and the env override ($.state is per session and starts empty after /clear).
export type PassagemFase = 'ocioso' | 'aguardando' | 'escrevendo' | 'contando' | 'pronta'

declare module 'claude-code' {
  interface PluginState {
    'sync_relay': {
      tokens: number | null
      piso: number | null
      adiado: number | null
      fase: PassagemFase
      auto: boolean
      apresentado: boolean
      interativo: boolean
      restante: number
      demorou: boolean
      limiar: number
      botao: boolean
      compact: { c: number; origem: string } | null
      carregado: boolean
    }
  }
}
