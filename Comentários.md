
# Devolutiva formativa — Atividade 01 da SA

**Estudante:** Yasmin  
**Turma:** Rio Negrinho — Tarde  
**Unidade Curricular:** Programação de Aplicativos  
**Projeto:** Sistema de Delivery  
**Códigos analisados:** `codigo/app.py`, `codigo/db.py` e `codigo/regras.py`  
**Referência:** Situação de Aprendizagem nº 1 — *Da Ideia ao Código*

## O que você já conseguiu desenvolver

Yasmin, seu projeto apresenta uma estrutura de aplicação de delivery com diferentes operações relacionadas a clientes, restaurantes, produtos, entregadores e pedidos. Você organizou as responsabilidades em arquivos específicos e utilizou recursos importantes de Python, Flask e SQLite.

Pontos positivos identificados:

- Separou **aplicação, acesso ao banco de dados e regras de negócio** nos arquivos `app.py`, `db.py` e `regras.py`.
- Utilizou **funções reutilizáveis** para consultar, salvar, atualizar e excluir registros.
- Criou rotas para cadastro e gerenciamento de diferentes entidades do sistema.
- Implementou **validações de entradas**, incluindo telefone, e-mail, preços e quantidades.
- Utilizou **consultas SQL parametrizadas**, reduzindo riscos associados à montagem de consultas com dados do usuário.
- Aplicou transações com `commit()` e `rollback()` em operações de banco.
- Representou valores monetários em centavos, evitando depender de cálculos com números de ponto flutuante.
- Organizou regras para situações dos pedidos e transições permitidas.
- Incluiu comentários e docstrings que ajudam a compreender as responsabilidades das funções.

## O que precisa ser corrigido

### 1. Incluir os arquivos necessários para inicializar o banco

O arquivo `db.py` utiliza `schema.sql` e `seed.sql` para criar a estrutura do banco e carregar dados de exemplo.

Entretanto, esses arquivos não foram encontrados na pasta `codigo/` da versão principal consultada.

**Como melhorar:** incluir os scripts SQL exigidos pela aplicação ou ajustar os caminhos de leitura para arquivos que realmente existam no repositório.

Sem esses arquivos, a inicialização de um novo banco não poderá ser concluída conforme o código apresentado.

### 2. Disponibilizar os templates utilizados pelo Flask

O arquivo `app.py` utiliza `render_template()` para carregar páginas como `index.html`, `form.html` e outras.

Entretanto, os arquivos HTML necessários não aparecem na estrutura consultada. Os arquivos existentes na pasta `interface/` estão vazios.

**Como melhorar:** criar os templates esperados na pasta reconhecida pelo Flask ou configurar corretamente o diretório que será utilizado.

A construção completa da interface pertence a uma etapa posterior da SA, mas, como o programa já depende desses arquivos, sua ausência impede a demonstração integral das rotas correspondentes.

### 3. Revisar as configurações de segurança

O código define uma chave de sessão fixa e utiliza `app.run(debug=True)`.

Essas configurações podem servir ao desenvolvimento local, mas não devem ser mantidas dessa forma na publicação da aplicação.

**Como melhorar:** utilizar configurações de ambiente para informações sensíveis e desativar o modo de depuração fora do ambiente de desenvolvimento.

## Oportunidades de melhoria

### 4. Organizar a documentação específica do projeto

O README ainda precisa apresentar as informações necessárias para outro programador executar o sistema.

**Como melhorar:** incluir o objetivo do delivery, a estrutura dos módulos, as dependências, os procedimentos para inicializar o banco e os comandos de execução.

### 5. Criar testes automatizados para as regras de negócio

O código apresenta funções que podem ser testadas isoladamente, principalmente em `regras.py`. A documentação interna menciona testes, mas não identifiquei os arquivos correspondentes no repositório consultado.

**Como melhorar:** criar testes para conversão monetária, validações, cálculo de totais e transições de situações dos pedidos.

### 6. Verificar a integração entre os módulos

A organização em arquivos separados é positiva, mas depende da disponibilidade e da compatibilidade dos recursos utilizados por cada módulo.

**Como melhorar:** executar testes de integração entre aplicação, banco e templates, verificando se os caminhos dos arquivos e as operações funcionam em conjunto.

### 7. Continuar aprimorando o tratamento de erros

O código já trata várias situações inválidas. Na evolução do projeto, será importante distinguir problemas de validação, falhas de acesso ao banco e situações em que um registro não existe.

**Como melhorar:** manter mensagens claras para o usuário e registrar informações técnicas necessárias para identificar falhas durante o desenvolvimento.

## Testes recomendados

1. Instalar as dependências e iniciar o sistema em um ambiente novo.
2. Executar a criação das tabelas do banco.
3. Verificar a abertura das rotas que utilizam templates.
4. Cadastrar e consultar clientes, restaurantes e produtos.
5. Testar entradas inválidas e registros duplicados.
6. Registrar pedidos e conferir o cálculo dos valores.
7. Testar as transições de situação de um pedido.
8. Simular erros durante gravações para verificar o comportamento das transações.
9. Executar testes específicos das funções de `regras.py`.

## Prioridades para a próxima versão

1. **Incluir ou corrigir os caminhos dos scripts de inicialização do banco.**
2. **Disponibilizar os templates necessários para executar as rotas.**
3. **Documentar as dependências e o procedimento de execução.**
4. **Revisar as configurações de segurança.**
5. **Criar testes de regras de negócio e integração.**

## Mensagem final

Yasmin, seu código demonstra uma boa compreensão de **modularização, funções, validação de dados, rotas, regras de negócio e integração entre componentes**. A separação das responsabilidades e o uso de consultas parametrizadas são pontos positivos importantes.

O principal desafio agora é garantir que todos os arquivos necessários estejam disponíveis e que a aplicação possa ser executada de forma completa em outro computador. **Continue valorizando a organização do código, a documentação e os testes.** Esses cuidados são essenciais para transformar uma boa estrutura técnica em um sistema confiável e utilizável.
