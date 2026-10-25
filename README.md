# MMM com Google Meridian — Etapa 1

Desenho e configuração científica do TCC sobre o diferencial GEO. **Nenhuma posterior ou resultado de marketing foi estimado.** Dados públicos sintéticos; etapa limitada à preparação e auditoria.

1. Leia o [guia científico único](docs/01_DESENHO_CIENTIFICO_DIDATICO.md).
2. Execute o [notebook único](notebooks/01_DESENHO_CIENTIFICO_COLAB.ipynb) ou [abra no Colab](https://colab.research.google.com/github/thiagossilva17/MMM_Google_Meridian_ModelagemEtapa1/blob/main/notebooks/01_DESENHO_CIENTIFICO_COLAB.ipynb).
3. Consulte [configuração GEO](configs/baseline_geo.yaml), [validação](configs/validation_design.yaml) e [experimentos futuros](configs/experiment_registry.yaml).
4. Confira [proveniência](data/metadata/provenance.json), [manifesto executado](outputs/logs/run_manifest.json) e [aceitação](outputs/tables/acceptance.csv).

## Execução local

Python 3.12 recomendado. `requirements.txt` declara dependências diretas; `requirements-lock.txt` congela o ambiente efetivamente validado. Para repetir exatamente o código, faça checkout do commit de entrega exibido no histórico antes da execução.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m src.run_stage1
python -m pytest -q
```

No Windows, ative com `.venv\Scripts\activate`. Sem Meridian, `python -m src.run_stage1 --without-api` permite auditoria parcial e registra `spec_ready=BLOCKED`; não substitui validação integral.

A cópia oficial do CSV é versionada e validada por hash. Downloads de recuperação usam apenas URL imutável do Google. Não há Drive, token, serviço pago ou GPU obrigatórios. A instalação das dependências do Meridian pode ser volumosa mesmo sem amostragem.

## Estado e próximos passos

InputData, ModelSpec e estrutura do modelo foram validados localmente, incluindo a máscara resolvida. O holdout contém 936 células de teste e 5.304 de treino. Há seis alertas de cobertura local de Channel2 mantidos como REVIEW.

**Colab hospedado: NOT_TESTED_IN_HOSTED_COLAB.** As células foram verificadas sequencialmente via IPython no mesmo processo; a abertura de kernel Jupyter foi bloqueada por restrições de sockets. Isso não comprova execução no serviço. H-COMP segue PENDING_METHOD_DECISION; priors, pressupostos e suporte continuam sujeitos à revisão científica. Consulte o guia antes da Entrega 2. Este repositório não inicia a próxima etapa automaticamente.
