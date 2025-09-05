from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
import config

def create_retriever(k=10, top_n=7):
    embeddings = HuggingFaceEmbeddings(model_name=config.SENTENCE_TRANSFORMER_MODEL_NAME)
    base_vectorstore = FAISS.load_local(config.VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    base_retriever = base_vectorstore.as_retriever(search_kwargs={"k": k})

    reranker_model = HuggingFaceCrossEncoder(model_name=config.RERANKER_MODEL_NAME)
    compressor = CrossEncoderReranker(model=reranker_model, top_n=top_n)

    retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    return retriever
