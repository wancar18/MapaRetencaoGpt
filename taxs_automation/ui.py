"""Interfaces Tkinter utilizadas pela automação."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tkinter import BooleanVar, Entry, IntVar, Label, StringVar, Tk, Toplevel, filedialog, messagebox

from .text_utils import formatar_cnpj


@dataclass
class ConfiguracaoUnidade:
    nome_unidade: str
    substituto_tributario: bool
    possui_cebas: bool
    preencher_chamado: bool


def selecionar_pasta_notas() -> Optional[Path]:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    pasta = filedialog.askdirectory(title="Selecione a pasta com as NFS-e (PDF)")
    root.destroy()
    if not pasta:
        print("Processo cancelado pelo usuário ao selecionar pasta.")
        return None
    return Path(pasta)


def perguntar_configuracoes_unidade() -> Optional[ConfiguracaoUnidade]:
    root = Tk()
    root.title("Configurações iniciais")
    root.attributes("-topmost", True)

    nome_var = StringVar()
    substituto_var = IntVar()
    cebas_var = IntVar()
    chamado_var = IntVar()

    Label(root, text="Nome da unidade (obrigatório):").grid(row=0, column=0, sticky="w")
    nome_entry = Entry(root, textvariable=nome_var, width=40)
    nome_entry.grid(row=0, column=1, padx=10, pady=5)
    nome_entry.focus()

    Label(root, text="É substituto tributário?").grid(row=1, column=0, sticky="w")
    Entry(root, textvariable=substituto_var).grid(row=1, column=1, padx=10, pady=5)

    Label(root, text="Possui CEBAS?").grid(row=2, column=0, sticky="w")
    Entry(root, textvariable=cebas_var).grid(row=2, column=1, padx=10, pady=5)

    Label(root, text="Preencher campo 'Chamado' automaticamente?").grid(row=3, column=0, sticky="w")
    Entry(root, textvariable=chamado_var).grid(row=3, column=1, padx=10, pady=5)

    resultado: dict[str, Optional[ConfiguracaoUnidade]] = {"valor": None}

    def confirmar() -> None:
        nome = nome_var.get().strip()
        if not nome:
            messagebox.showerror("Validação", "O nome da unidade é obrigatório para continuar.")
            return
        resultado["valor"] = ConfiguracaoUnidade(
            nome_unidade=nome.upper(),
            substituto_tributario=bool(substituto_var.get()),
            possui_cebas=bool(cebas_var.get()),
            preencher_chamado=bool(chamado_var.get()),
        )
        root.destroy()

    def cancelar() -> None:
        root.destroy()

    Label(root, text="(Use 1 para SIM e 0 para NÃO)").grid(row=4, column=0, columnspan=2, pady=(5, 10))

    from tkinter import Button  # import tardio para evitar overhead

    Button(root, text="Confirmar", command=confirmar).grid(row=5, column=0, pady=10)
    Button(root, text="Cancelar", command=cancelar).grid(row=5, column=1, pady=10)

    root.mainloop()
    return resultado["valor"]


def confirmar_cnpj_tomador(candidatos: list[str]) -> Optional[str]:
    if not candidatos:
        return None
    root = Tk()
    root.title("Confirmação CNPJ tomador")
    root.attributes("-topmost", True)

    selecionado = StringVar(value=candidatos[0])

    for idx, cnpj in enumerate(candidatos):
        Label(root, text=f"CNPJ sugerido {idx + 1}: {formatar_cnpj(cnpj)}").pack(anchor="w")

    Entry(root, textvariable=selecionado, width=30).pack(pady=10)

    resultado: dict[str, Optional[str]] = {"valor": None}

    from tkinter import Button

    def aceitar() -> None:
        resultado["valor"] = selecionado.get()
        root.destroy()

    def recusar() -> None:
        resultado["valor"] = None
        root.destroy()

    Button(root, text="Confirmar", command=aceitar).pack(side="left", padx=10, pady=10)
    Button(root, text="Informar manualmente", command=recusar).pack(side="left", padx=10, pady=10)

    root.mainloop()

    if resultado["valor"]:
        return resultado["valor"]

    root = Tk()
    root.title("Informe o CNPJ do tomador")
    root.attributes("-topmost", True)
    manual = StringVar()
    Label(root, text="Digite o CNPJ do tomador:").pack()
    Entry(root, textvariable=manual).pack()

    def confirmar_manual() -> None:
        resultado["valor"] = manual.get()
        root.destroy()

    Button(root, text="Confirmar", command=confirmar_manual).pack(pady=10)
    root.mainloop()
    return resultado["valor"]
