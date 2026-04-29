https://www.zenml.io/blog/smolagents-vs-langgraph 
https://www.analyticsvidhya.com/blog/2025/01/smolagents-vs-langgraph/
https://www.geeksforgeeks.org/artificial-intelligence/langchain-vs-langgraph/
https://langfuse.com/guides/cookbook/integration_langgraph
https://www.promptingguide.ai/research/llm-agents
https://www.superannotate.com/blog/multi-agent-llms
https://blog.alexewerlof.com/p/multi-agent-system-reliability
https://dev.to/hargun_singh/-building-an-ai-agent-with-rag-a-simple-guide-to-vector-databases-and-embeddings-2ch4
https://learnopencv.com/vector-db-and-rag-pipeline-for-document-rag/
https://devdocs.io/fastapi/

https://www.twilio.com/docs/messaging/quickstart
to help decide which to use and why.


Research Summary

ZenML — “Smolagents vs LangGraph”
I used this article to compare different agent frameworks and understand why LangGraph was a better fit for my project than a lighter code-based agent framework like Smolagents. The article explained that LangGraph is built around explicit graph workflows with nodes, edges, branching, loops, and persistent state, which helped me understand how to structure my assistant as a controlled workflow instead of one large unpredictable agent.

Analytics Vidhya — “Smolagents vs LangGraph”
I used this resource to better understand the strengths and limitations of LangGraph compared to other agent frameworks. It helped me think through tradeoffs such as complexity, debugging, and when a more structured multi-agent workflow is worth using instead of a simpler agent setup.

GeeksforGeeks — “LangChain vs LangGraph”
I used this article to understand the difference between LangChain and LangGraph. It helped me explain that LangChain provides useful building blocks for LLMs, prompts, APIs, tools, and retrieval, while LangGraph is better for connecting those pieces into more complex workflows with branching and state.

Langfuse — “LangGraph Integration”
I used this guide to learn about observability and debugging for LangGraph applications. Since my project uses multiple agents and tool calls, this helped me understand the importance of tracing what happens inside the graph, monitoring agent steps, and improving reliability when the system makes mistakes. The guide also describes LangGraph as a framework for stateful, multi-agent applications with persistence and recovery support.

Prompting Guide — “LLM Agents”
I used this as a general research source for understanding how LLM agents work. It helped me understand common agent components such as planning, memory, tool use, and reasoning. It also helped me understand major challenges with agents, including hallucinations, prompt reliability, limited context length, cost, and the difficulty of making agents consistent.

SuperAnnotate — “Multi-agent LLMs”
I used this article to understand the purpose of multi-agent systems. It helped me explain why my project separates responsibilities into specialized agents, such as weather, trail information, first aid, camping advice, email, and search. The article describes multi-agent systems as breaking large tasks into smaller subtasks handled by specialized agents, which matches the architecture of my assistant.

Alex Ewerlöf — “Multi-Agent System Reliability”
I used this article to think about reliability problems in multi-agent systems. It helped me understand that adding more agents can also add more failure points, such as hallucinations, context drift, and harder debugging. This influenced my focus on guardrails, fallbacks, routing, and limiting agent loops instead of just assuming that more agents automatically make the system better.

DEV Community — “Building an AI Agent with RAG”
I used this guide to understand how retrieval-augmented generation works with embeddings and vector databases. It helped me understand the basic RAG pipeline: split documents into chunks, convert them into embeddings, store them in a vector database, and retrieve relevant chunks when the user asks a question. This was useful for thinking about how an assistant can answer from stored knowledge instead of relying only on the LLM’s memory.

LearnOpenCV — “Vector DB and RAG Pipeline”
I used this article to better understand vector databases and document-based RAG pipelines. It explained how vector databases store embeddings and perform semantic similarity search, which helped me understand how large documents or knowledge sources can be searched efficiently without putting everything into the LLM context at once. This was useful for designing a more scalable knowledge-retrieval layer for the assistant.

Twilio — “Quickstart”
I used this guide to understand how to use Twilio’s SMS API for sending and receiving messages. It helped me understand the basic flow of sending an SMS, receiving a webhook, and parsing the message in the webhook handler. This was useful for integrating SMS functionality into the assistant.

FastAPI — “Documentation”
I used this reference to understand the FastAPI framework and how to use it to build the web application. It helped me understand the basic concepts of FastAPI, such as routes, endpoints, request/response models, and dependency injection. This was useful for designing the API endpoints and web application structure.

documentation reference:
https://developers.google.com/workspace/gmail/api/reference/rest gmail api documentation

