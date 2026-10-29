"""
文档解析器
支持 PDF 和 Word 文档的文本提取
"""
import os
from typing import Optional
import fitz  # PyMuPDF
from docx import Document


class DocumentParser:
    """文档解析工具类"""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """
        从 PDF 文件提取文本
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        text_parts = []
        try:
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
        except Exception as e:
            raise ValueError(f"PDF 解析失败: {str(e)}")
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """
        从 Word 文档提取文本
        
        Args:
            file_path: Word 文件路径
            
        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            raise ValueError(f"Word 文档解析失败: {str(e)}")
    
    @staticmethod
    def extract_text(file_path: str) -> str:
        """
        自动识别文件类型并提取文本
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".pdf":
            return DocumentParser.extract_text_from_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return DocumentParser.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")
    
    @staticmethod
    def truncate_text(text: str, max_chars: int = 15000) -> str:
        """
        截断文本以避免超出 AI 模型的上下文限制
        
        Args:
            text: 原始文本
            max_chars: 最大字符数
            
        Returns:
            截断后的文本
        """
        if len(text) <= max_chars:
            return text
        
        # 保留开头和结尾，中间截断
        half = max_chars // 2
        return text[:half] + "\n\n... [内容过长，已截断] ...\n\n" + text[-half:]
