from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import UTC, datetime

Base = declarative_base()

class Technician(Base):
    __tablename__ = 'technicians'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    gender = Column(String, nullable=True)      # 新增性别字段
    strength = Column(String, nullable=True)    # 新增力气/倾向性字段
    schedules = relationship("TechnicianSchedule", back_populates="technician", cascade="all, delete-orphan")

class TechnicianSchedule(Base):
    __tablename__ = 'technician_schedules'
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)  # 'busy' or 'free'
    appointment_id = Column(Integer, nullable=True)
    technician = relationship("Technician", back_populates="schedules")

class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    keywords = Column(JSON, nullable=True)  # 存储关键词列表
    embedding = Column(JSON, nullable=True)  # 存储嵌入向量
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Integer, default=1)  # 软删除标记


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_name", "version", name="uq_prompt_name_version"),)

    id = Column(Integer, primary_key=True)
    prompt_name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    change_note = Column(String, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

class UserBehavior(Base):
    __tablename__ = 'user_behaviors'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, default='default_user')  # 单用户场景使用默认用户ID
    action_type = Column(String, nullable=False)  # 'appointment', 'consultation', 'inquiry'
    action_data = Column(JSON, nullable=True)  # 存储行为相关的详细数据
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    technician = relationship("Technician")

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, default='default_user')
    preference_type = Column(String, nullable=False)  # 'technician', 'time', 'service', 'duration'
    preference_value = Column(String, nullable=False)
    confidence_score = Column(Integer, default=1)  # 偏好的置信度（出现次数）
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserRecommendation(Base):
    __tablename__ = 'user_recommendations'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, default='default_user')
    recommendation_type = Column(String, nullable=False)  # 'technician_available', 'return_reminder', 'service_suggestion'
    content = Column(Text, nullable=False)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)
    is_sent = Column(Integer, default=0)  # 是否已发送
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    technician = relationship("Technician")


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    workflow_id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False, index=True)
    workflow_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    fields = Column(JSON, nullable=False, default=dict)
    missing_fields = Column(JSON, nullable=False, default=list)
    assumptions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    audit_logs = relationship(
        "WorkflowAuditLog",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowAuditLog.id",
    )


class WorkflowAuditLog(Base):
    __tablename__ = "workflow_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String, ForeignKey("workflow_instances.workflow_id"), nullable=False, index=True)
    action = Column(String, nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    workflow = relationship("WorkflowInstance", back_populates="audit_logs")
