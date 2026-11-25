import { describe, expect, it } from 'vitest';
import { translations } from '@/i18n/translations';
import type { AnswerGoal } from '@/modules/labelings/labelingsTypes';
import { firstYoutubeId, goalBar, goalBarLabel, goalHeaderLabel, paceLines } from './goal';

const t = (key: string, vars: Record<string, string | number> = {}) =>
  (translations['pt-BR'][key] ?? key).replace(/\{\{(\w+)\}\}/g, (_, k) => String(vars[k]));

const base: AnswerGoal = {
  target: 150, done: 10, next_milestone: 150, before_missing: 0, to_go: 140,
  deadline: '2026-12-15', days_left: 15, per_week: 47, per_day: 10,
};

describe('goal', () => {
  it('shows the weekly pace first and the daily figure second', () => {
    const pace = paceLines(base, t, 'pt-BR');
    expect(pace?.week).toBe('Faltam 140 registros: cerca de 47 por semana até 15 de dezembro');
    expect(pace?.day).toBe('ou 10 por dia');
  });

  it('counts the missing Parte 1 records in the pace', () => {
    const pace = paceLines({ ...base, done: 0, before_missing: 40, to_go: 190, per_week: 64 }, t, 'pt-BR');
    expect(pace?.week).toBe('Faltam 40 + 150 registros: cerca de 64 por semana até 15 de dezembro');
  });

  it('hides the pace after the deadline or once the target is reached', () => {
    expect(paceLines({ ...base, per_week: null, per_day: null }, t, 'pt-BR')).toBeNull();
  });

  it('moves the bar to the next milestone after the target', () => {
    const g = { ...base, done: 163, next_milestone: 200, to_go: 0, per_week: null, per_day: null };
    expect(goalBar(g)).toEqual({ value: 163, max: 200 });
    expect(goalBarLabel(g, t)).toBe('163 registros · próxima marca: 200');
    expect(goalHeaderLabel(g, t)).toBe('163 registros · próxima marca: 200');
  });

  it('compact header shows this week\'s target while a pace exists', () => {
    expect(goalHeaderLabel(base, t)).toBe('10 de 150 · meta desta semana: 47');
    expect(goalHeaderLabel({ ...base, per_week: null, per_day: null }, t)).toBe('10 de 150 registros');
  });

  it('finds the first YouTube link', () => {
    expect(firstYoutubeId('[Tutorial](https://youtu.be/5byUtzKvO7w). Mais')).toBe('5byUtzKvO7w');
    expect(firstYoutubeId('https://www.youtube.com/watch?v=5byUtzKvO7w')).toBe('5byUtzKvO7w');
    expect(firstYoutubeId('sem vídeo')).toBeNull();
  });
});
