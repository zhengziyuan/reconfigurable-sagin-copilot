import { useCallback, useReducer } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ScenarioShape } from "../types";

export interface EditorSnapshot {
  scenario: ScenarioShape;
  selectedCandidateIds: string[];
}
interface History {
  present: EditorSnapshot;
  past: EditorSnapshot[];
  future: EditorSnapshot[];
}
type Action = { type: "edit"; update: (current: EditorSnapshot) => EditorSnapshot }
  | { type: "reset"; snapshot: EditorSnapshot } | { type: "undo" } | { type: "redo" };

function reducer(state: History, action: Action): History {
  if (action.type === "reset") return { present: action.snapshot, past: [], future: [] };
  if (action.type === "undo") {
    if (!state.past.length) return state;
    return { present: state.past[state.past.length - 1], past: state.past.slice(0, -1), future: [state.present, ...state.future] };
  }
  if (action.type === "redo") {
    if (!state.future.length) return state;
    return { present: state.future[0], past: [...state.past, state.present].slice(-50), future: state.future.slice(1) };
  }
  const next = action.update(state.present);
  if (JSON.stringify(next) === JSON.stringify(state.present)) return state;
  return { present: next, past: [...state.past, state.present].slice(-50), future: [] };
}

function resolve<T>(value: SetStateAction<T>, current: T): T {
  return typeof value === "function" ? (value as (previous: T) => T)(current) : value;
}

export function useScenarioEditor(initial: EditorSnapshot) {
  const [history, dispatch] = useReducer(reducer, { present: initial, past: [], future: [] });
  const setScenario: Dispatch<SetStateAction<ScenarioShape>> = useCallback((value) => {
    dispatch({ type: "edit", update: (current) => ({ ...current, scenario: resolve(value, current.scenario) }) });
  }, []);
  const setSelectedCandidateIds: Dispatch<SetStateAction<string[]>> = useCallback((value) => {
    dispatch({ type: "edit", update: (current) => ({ ...current, selectedCandidateIds: resolve(value, current.selectedCandidateIds) }) });
  }, []);
  const update = useCallback((updater: (current: EditorSnapshot) => EditorSnapshot) => dispatch({ type: "edit", update: updater }), []);
  const reset = useCallback((snapshot: EditorSnapshot) => dispatch({ type: "reset", snapshot }), []);
  return { ...history.present, setScenario, setSelectedCandidateIds, update, reset,
    canUndo: history.past.length > 0, canRedo: history.future.length > 0,
    undo: () => dispatch({ type: "undo" }), redo: () => dispatch({ type: "redo" }) };
}
