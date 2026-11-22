# DebtLedger: o extrato da dívida técnica

Trabalho integrador de Tópicos em Engenharia de Software (LegacyTech: IA para evolução de sistemas legados).

Quem já pegou um sistema legado para manter conhece a cena: você abre um arquivo e encontra um `# TODO: refatorar isso` de 2019, um `# HACK` que ninguém lembra por que existe e um `# só o Carlos sabe` (e o Carlos saiu da empresa faz dois anos). Esses comentários são o que a literatura chama de **dívida técnica autoadmitida** (SATD, *self-admitted technical debt*). A pessoa sabia que estava deixando um problema para trás e anotou.

O problema é que, num sistema grande, são centenas desses comentários e a equipe não tem tempo para pagar todos. A pergunta que importa no dia a dia não é "onde tem dívida?", e sim **"qual dívida está me custando mais caro agora?"**. Foi em cima dessa pergunta que eu montei a ferramenta.

## A ideia

Peguei a metáfora do Ward Cunningham ao pé da letra e tratei cada comentário como um item de extrato bancário:

- **Principal** é quanto custa quitar a dívida (horas de trabalho para resolver).
- **Juros** é quanto a dívida cobra enquanto continua lá. Um TODO num arquivo que ninguém abre há cinco anos quase não cobra nada. O mesmo TODO numa função gigante que a equipe altera toda semana cobra caro, porque cada mudança ali fica mais lenta e mais arriscada.

A parte que eu acho mais interessante é a divisão do trabalho:

| O quê | Quem calcula | Por quê |
|---|---|---|
| Juros | métricas medidas no código e no git (sem IA) | é a base da prioridade, então precisa ser um fato e não um palpite |
| Tipo de dívida, causa, esforço, estratégia | IA (Claude) | exige ler e interpretar código e texto livre, coisa que regra fixa faz mal |
| Se a resposta da IA é confiável | verificador automático + revisão humana | IA erra, e o erro precisa aparecer antes de virar tarefa no backlog |

## O que a ferramenta faz

```
repositório ──► 1. coleta ──► 2. métricas ──► 3. análise ──► 4. verificação ──► 5. prioridade ──► extrato.html
                 (regex)      (git + AST)      (Claude)       (checagens)        + ledger.json      backlog.md
```

1. **Coleta.** Varre o código atrás de comentários com cara de dívida (TODO, FIXME, HACK, XXX, "gambiarra", "temporário", "copiado de", "chumbado", "só fulano sabe"...). A regex é de propósito generosa: prefiro pegar falso positivo e deixar a IA filtrar a perder dívida de verdade.
2. **Métricas.** Para cada comentário a ferramenta mede:
   - a complexidade ciclomática da função onde ele está (via `ast` do Python);
   - quantos commits o arquivo teve nos últimos 12 meses (`git log`);
   - quantas pessoas já mexeram no arquivo (se foi uma só, tem dívida de conhecimento junto);
   - quando o comentário foi escrito e por quem (`git blame`).
3. **Análise com IA.** O Claude recebe o comentário, o trecho de código e as métricas e devolve um JSON validado por schema com: se é dívida mesmo, tipo (taxonomia de Alves et al., 2016), quadrante de Fowler (deliberada/inadvertida, prudente/imprudente), risco, esforço (P/M/G), estratégia, primeiro passo e um título de issue.
4. **Verificação.** Antes de mostrar qualquer coisa, a ferramenta confere a resposta da IA (detalhes logo abaixo).
5. **Prioridade e registro.** Calcula juros, converte o esforço em horas, classifica cada item num quadrante (pagar agora, planejar, pagar quando passar por perto, monitorar) e atualiza o `ledger.json`, que guarda o histórico entre execuções.

Saídas, todas em `<repositório>/.debtledger/`:

- `extrato.html`: o relatório visual (gráfico juros × principal, ranking, detalhes de cada item com as checagens);
- `backlog.md`: os itens já no formato de issue, para copiar para o GitHub/Jira;
- `itens.json`: tudo em formato estruturado;
- `ledger.json`: o registro da dívida ao longo do tempo;
- `cache_ia.json`: respostas da IA já recebidas (rodar de novo não gasta API).

### Como a resposta da IA é verificada

Essa foi a parte em que eu mais pensei, porque "mandar o código para o chatbot e copiar a resposta" é exatamente o que o enunciado pede para não fazer. Cada análise passa por estas checagens:

- **Evidência literal.** A IA é obrigada a citar o trecho do código que justifica a classificação. A ferramenta procura essa citação no código real. Se não achar, é sinal de alucinação, e o item é marcado como **suspeito**.
- **Formato.** Todos os campos precisam estar dentro da taxonomia (o schema já força isso, mas confiro de novo).
- **Confiança.** Se a própria IA declara confiança abaixo de 0,6, o item vai para revisão.
- **Segunda opinião.** Uma heurística simples por palavras-chave também classifica o item. Se ela e a IA discordam (e os tipos não são vizinhos, tipo design × código), o item vai para revisão.
- **Coerência com as métricas.** Se a IA diz que dá para refatorar em meio dia uma função com complexidade 22, a ferramenta avisa que a estimativa parece otimista.
- **"Não é dívida".** Quando a IA diz que um comentário não é dívida, o item não some. Ele vai para o fim da lista e fica marcado para alguém confirmar.

O resultado é um status por item: **consistente**, **revisar** ou **suspeita**. Mesmo "consistente" continua sendo sugestão: a decisão final é de quem mantém o sistema, e ela fica registrada no `ledger.json` (campo `decisao`: `aceita`, `falso_positivo`, `em_andamento` ou `agendada`). Nas próximas execuções a ferramenta respeita essa decisão.

### Gestão ao longo do tempo

Cada item ganha um id que depende do arquivo e do texto do comentário, não do número da linha. Assim, se alguém inserir código acima do TODO, ele continua sendo o mesmo item. A cada execução o ledger compara com a anterior e mostra o que é **novo**, o que foi **quitado** (o comentário sumiu do código) e o que foi **reaberto**. É isso que transforma um relatório avulso em acompanhamento da dívida.

## Como rodar

Precisa de Python 3.10+ e git instalados.

```bash
pip install -r requirements.txt

# 1) cria o sistema legado de exemplo (SIGAFIN) em demo/sigafin
python exemplo/criar_sigafin.py

# 2) roda a análise
python -m debtledger demo/sigafin

# 3) abre demo/sigafin/.debtledger/extrato.html no navegador
```

### Com IA (Claude)

Sem credencial, a ferramenta roda sozinha em **modo offline**, usando só a heurística, e o relatório avisa isso em destaque. Para usar o Claude, crie uma chave em https://console.anthropic.com e defina a variável de ambiente antes de rodar:

```powershell
# PowerShell
$env:ANTHROPIC_API_KEY = "sua-chave-aqui"
python -m debtledger demo/sigafin --modo ia
```

```bash
# bash / Git Bash
export ANTHROPIC_API_KEY="sua-chave-aqui"
python -m debtledger demo/sigafin --modo ia
```

Opções úteis:

| Opção | Padrão | O que faz |
|---|---|---|
| `--modo` | `auto` | `auto` usa IA se achar a chave; `ia` exige IA; `offline` só heurística |
| `--modelo` | `claude-opus-5-5` | modelo do Claude; `claude-haiku-5-5` sai bem mais barato |
| `--esforco` | `low` | nível de raciocínio do modelo; para classificar, `low` resolve |
| `--limite` | `40` | máximo de itens mandados para a IA por execução |
| `--saida` | `<repo>/.debtledger` | pasta dos relatórios |

O exemplo tem 12 comentários, então são 12 chamadas à API. Com o Opus 5.5 isso dá bem menos de 1 dólar, e as próximas execuções usam o cache.

> Nunca coloque a chave no código nem suba ela pro GitHub. O `.gitignore` já ignora `.env`.

### Demonstração da evolução (dívida paga e dívida nova)

```bash
python exemplo/criar_sigafin.py --etapa 2   # a equipe documenta o CSV, põe timeout no banco e cria um TODO novo
python -m debtledger demo/sigafin
```

O terminal e o relatório passam a mostrar "1 nova, 2 quitadas".

### Testes

```bash
python -m unittest discover -s tests -v
```

São 10 testes. Eles cobrem a coleta, as métricas do git, o cálculo de juros, o ledger entre execuções e o caminho da IA, com um cliente falso da API: um teste manda uma resposta com evidência inventada e confere se o verificador marca como suspeita.

### Rodando num projeto real

Funciona em qualquer repositório git com código em Python, JavaScript/TypeScript, Java, C#, C/C++, Go, PHP, Kotlin, Ruby ou shell:

```bash
git clone https://github.com/<algum-projeto-legado>.git
python -m debtledger <pasta-do-projeto> --modo ia --limite 20
```

Para linguagens que não são Python, a complexidade é aproximada (conto `if/for/while/case/catch/&&/||` numa janela de 40 linhas). O relatório deixa isso visível.

## Sobre o exemplo (SIGAFIN)

O SIGAFIN é um **sistema fictício**, criado por mim para a demonstração. É o faturamento de uma distribuidora, em produção "desde 2019". O script `exemplo/criar_sigafin.py` monta o repositório com 21 commits entre 2019 e 2026, feitos por quatro pessoas inventadas, para que as métricas de histórico tenham o que medir. As dívidas plantadas são as que eu mais vejo em legado:

- `calcular_nota()`: função com complexidade 22 que todo mundo altera (regra de desconto, frete, cupom, imposto...);
- alíquota de imposto chumbada no código;
- conexão com o banco antigo sem timeout, num arquivo que só uma pessoa mexeu;
- layout de exportação que "só o Carlos sabe";
- função de arredondamento copiada entre módulos;
- validação de CPF/CNPJ pedida pelo cliente em 2021 e nunca feita;
- um falso positivo de propósito (`arquivo temporario ... e apagado`), para ver se a IA percebe que aquilo não é dívida.

## Relação com o conteúdo da disciplina

- **Metáfora da dívida (Cunningham, 1992):** principal e juros viraram números de verdade. O ranking usa "juros evitados por hora investida", que é o raciocínio de custo-benefício para decidir o que pagar.
- **Tipos de dívida (Alves et al., 2016):** arquitetura, design, código, teste, documentação, defeito, requisito, build, infraestrutura e pessoas. A IA classifica dentro dessa lista e não pode inventar categoria.
- **Quadrante de Fowler (2009):** deliberada × inadvertida e prudente × imprudente. Ajuda a entender a causa: um `HACK` consciente para cumprir prazo é diferente de código ruim feito sem saber.
- **SATD (Potdar & Shihab, 2014; Maldonado & Shihab, 2015):** a fonte dos itens são os comentários em que a própria equipe admitiu a dívida.
- **Hotspots (Tornhill, *Your Code as a Crime Scene*):** complexidade × frequência de mudança como indicador de onde o custo de manutenção se concentra. É a base dos juros.
- **Dívida de conhecimento:** arquivo com um único autor aumenta o risco (o "fator ônibus").
- **Gestão da dívida:** identificação → medição → priorização → registro → acompanhamento. O ledger e o backlog cobrem as etapas de registro e acompanhamento, que costumam ficar de fora das ferramentas.
- **Leis de Lehman:** o sistema que continua evoluindo tende a ficar mais complexo se ninguém trabalha para reduzir isso. Os juros medem justamente onde essa degradação está acontecendo.

## O que tem de diferente das ferramentas que já existem

| Ferramenta | O que faz | O que eu fiz diferente |
|---|---|---|
| DebtViz, SATDBailiff | detectam SATD com ML e acompanham no histórico | além de detectar, digo **quanto cada item custa** combinando com métricas de hotspot |
| TagDebt | classifica dívida em issues do GitHub | trabalho direto no código e gero a issue pronta |
| AnaConDebt | apoia a avaliação de juros e a priorização, com estimativas manuais | os juros saem automaticamente do git; só o principal é estimado |
| Arcan, ATDx | métricas de dívida arquitetural | olho para a dívida que a equipe declarou, em qualquer nível |

A combinação que eu não encontrei pronta é: **SATD + métricas de hotspot para juros + IA para interpretar + verificação automática da IA + registro entre execuções**.

## Limitações (sendo honesto)

- **Só enxerga a dívida que alguém anotou.** Código ruim sem comentário não aparece. Dá para combinar com SonarQube ou similares para cobrir isso.
- **A fórmula de juros é minha.** Os pesos (45% frequência, 30% complexidade, 15% idade, 10% conhecimento) fazem sentido para mim, mas não foram calibrados com dados reais de esforço. Estão em `debtledger/priorizacao.py`, fáceis de mudar.
- **Frequência de commits é por arquivo**, não por função. Uma função tranquila dentro de um arquivo movimentado herda juros altos.
- **O esforço estimado pela IA é a parte mais frágil.** Por isso ele pesa só no principal e o verificador confere se faz sentido com a complexidade.
- **A checagem de evidência pega citação inventada, mas não pega interpretação errada.** A IA pode citar uma linha real e mesmo assim tirar a conclusão errada. Essa parte só a revisão humana resolve.
- **Privacidade.** No modo IA, trechos do código vão para a API da Anthropic. Em empresa, isso precisa ser autorizado. O modo offline existe também por causa disso.
- **Não testei com a API real neste ambiente.** O caminho da IA está coberto por testes com cliente falso (formato do pedido, parse do JSON, cache, detecção de evidência inventada). Na primeira execução com chave vale conferir o resultado com calma.

## O que ficou planejado e não foi implementado

- Abrir as issues direto no GitHub (hoje gera o `backlog.md` para copiar).
- Rodar no CI a cada pull request e comentar "este PR adiciona 2 dívidas e quita 1".
- Detectar dívida não declarada (funções muito complexas sem nenhum comentário) e pedir à IA para sugerir o comentário.
- Calibrar os pesos dos juros com dados históricos de tempo gasto (por exemplo, tempo até fechar issues que mexem nos arquivos).
- Gráfico de evolução do total de juros ao longo das execuções.

## Estrutura

```
debtledger/
  coletor.py      busca dos comentários de dívida
  metricas.py     complexidade (AST) e histórico do git
  ia.py           análise com Claude + heurística offline
  verificador.py  checagens da resposta da IA
  priorizacao.py  juros, principal, quadrantes
  registro.py     ledger entre execuções
  relatorio.py    extrato.html, backlog.md, itens.json
  cli.py          linha de comando
exemplo/
  criar_sigafin.py  gera o sistema legado fictício com histórico git
tests/
  test_debtledger.py
```

## Serviços e modelos de IA usados

- **Claude Opus 5.5** (`claude-opus-5-5`), da Anthropic, pela API oficial (SDK `anthropic` para Python). Uso saída estruturada com JSON Schema e esforço `low`. O modelo pode ser trocado com `--modelo`.
- Nenhum modelo foi treinado para este trabalho.
- Nenhuma credencial está no repositório. A chave é lida da variável de ambiente `ANTHROPIC_API_KEY`.

## Referências

- Cunningham, W. *The WyCash Portfolio Management System*. OOPSLA, 1992.
- Fowler, M. *Technical Debt Quadrant*, 2009. https://martinfowler.com/bliki/TechnicalDebtQuadrant.html
- Alves, N. S. R. et al. *Identification and management of technical debt: A systematic mapping study*. IST, 2016.
- Potdar, A.; Shihab, E. *An exploratory study on self-admitted technical debt*. ICSME, 2014.
- Maldonado, E.; Shihab, E. *Detecting and quantifying different types of self-admitted technical debt*. MTD, 2015.
- Tornhill, A. *Your Code as a Crime Scene*. Pragmatic Bookshelf, 2015.
- Lehman, M. M. *Programs, life cycles, and laws of software evolution*. Proc. IEEE, 1980.
