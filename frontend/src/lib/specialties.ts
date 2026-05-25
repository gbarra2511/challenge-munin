// Especialidades: IDs fixos 1..8, bootstrap na migration (0001_initial.py).
// Não há endpoint /specialties — a lista é estável e vive no banco desde o início.
export const SPECIALTIES: ReadonlyArray<{ id: number; name: string }> = [
  { id: 1, name: "Clínica Médica" },
  { id: 2, name: "Pediatria" },
  { id: 3, name: "Cardiologia" },
  { id: 4, name: "Ginecologia e Obstetrícia" },
  { id: 5, name: "Ortopedia" },
  { id: 6, name: "Anestesiologia" },
  { id: 7, name: "Medicina Intensiva (UTI)" },
  { id: 8, name: "Pronto-Socorro" },
];

export const specialtyName = (id: number): string =>
  SPECIALTIES.find((s) => s.id === id)?.name ?? `Especialidade ${id}`;
