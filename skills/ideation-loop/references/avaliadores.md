# Avaliadores

O avaliador é o que separa ideia nova e boa de ideia que só soa nova. Estudos de ideação com LLM mostram que ideias julgadas mais novas antes da execução perdem nota depois de executadas, então o avaliador precisa estar o mais perto possível de execução real.

Escolha o mais forte disponível, de cima para baixo. Registre no `brief.md` qual foi escolhido e por quê.

## Nível 1. Métrica executável

Um script retorna um número e a ideia é implementável em código ou configuração.

Exemplos: latência p95 de um endpoint, custo em tokens por conversa de um agente, taxa de acerto de um classificador num conjunto rotulado, número de testes passando, tempo de uma query, taxa de conversão simulada sobre histórico.

Use o modo evolutivo (`modo-evolutivo.md`). É onde LLM produz soluções genuinamente novas com mais confiabilidade.

## Nível 2. Retroteste em dados históricos

A ideia faz uma previsão que pode ser checada no que já aconteceu.

Exemplos: "usuários que fazem X na primeira semana retêm mais" vira uma query de coorte; "horários ociosos se concentram em Y" vira uma agregação; "uma regra de priorização teria evitado Z" vira replay da regra sobre o log.

Formato do teste em `evidence/<id>.md`: hipótese, query ou script exato (somente leitura), resultado bruto, leitura do resultado, veredito. Se o resultado for ambíguo, diga ambíguo.

Cuidados: amostras pequenas, sobrevivência, correlação em vez de causa. Escreva o tamanho da amostra junto do resultado.

## Nível 3. Protótipo descartável

Construir a menor versão que mostra se o mecanismo funciona: um script que gera a saída que o usuário veria, um endpoint fake, um prompt rodando sobre 20 casos reais anonimizados.

O critério é o mecanismo funcionar, não ficar bonito. Limite de tempo: uma sessão. Não faça deploy em produção dentro do loop.

## Nível 4. Teste com pessoas (fica pendente)

Entrevista com 5 clientes, landing page, mensagem para uma base pequena. O loop não executa isso; prepara o roteiro e o critério de morte e deixa como próximo passo. Nunca envie nada a cliente sem confirmação explícita do usuário.

## Nível 5. Juízo estruturado (último recurso)

Quando nada acima é possível, o torneio cego da Fase 6 com critérios explícitos é o avaliador. Declare no relatório que a seleção foi por juízo, não por evidência, e trate o ranking como hipótese a testar.

## Custos que contam como evidência

Custo de infraestrutura e de tokens é verificável sem cliente: calcule com preços reais pesquisados na hora (não de memória) e volumes reais do banco. Uma ideia que custa mais do que gera morre aqui, cedo e barato.
