"""Chat business logic: contacts, friend requests, conversations, messages.

Every public method on ``ChatService`` assumes the caller has already
enforced the relevant permission gate.  The service enforces data-scope
rules: a user can only read/write conversations they are a member of,
and only send messages to active contacts (for private conversations).
"""

from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    Contact,
    Conversation,
    ConversationMember,
    FriendRequest,
    Message,
    MessageReadReceipt,
    User,
    utc_now,
)


class ChatService:
    """Aggregate service for chat domain operations."""

    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _is_contact(self, user_id: str, contact_id: str) -> bool:
        row = await self.session.get(Contact, (user_id, contact_id))
        return row is not None and row.status == "active"

    async def _assert_contact(self, user_id: str, contact_id: str) -> None:
        if not await self._is_contact(user_id, contact_id):
            raise ApiError(403, "FORBIDDEN", "对方不是你的联系人")

    async def _assert_conversation_member(self, conversation_id: str) -> None:
        member = await self.session.get(
            ConversationMember, (conversation_id, self.actor_id)
        )
        if member is None:
            raise ApiError(403, "FORBIDDEN", "你不是该会话的成员")

    def _user_to_dict(self, user: User) -> dict:
        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
        }

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------

    async def search_users(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """Search users by username or display name (exclude self)."""
        pattern = f"%{query}%"
        total_q = select(func.count(User.id)).where(
            User.id != self.actor_id,
            User.status == "active",
            (User.username.ilike(pattern) | User.display_name.ilike(pattern)),
        )
        total = (await self.session.scalar(total_q)) or 0

        rows = (
            (
                await self.session.scalars(
                    select(User)
                    .where(
                        User.id != self.actor_id,
                        User.status == "active",
                        (User.username.ilike(pattern) | User.display_name.ilike(pattern)),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [self._user_to_dict(u) for u in rows], total

    async def list_contacts(self) -> list[dict]:
        rows = (
            (
                await self.session.scalars(
                    select(Contact)
                    .options(selectinload(Contact.contact))
                    .where(Contact.user_id == self.actor_id, Contact.status == "active")
                )
            )
            .all()
        )
        results = []
        for c in rows:
            entry = self._user_to_dict(c.contact)
            entry["remark"] = c.remark
            entry["status"] = c.status
            entry["created_at"] = c.created_at.isoformat() if c.created_at else None
            results.append(entry)
        return results

    # ------------------------------------------------------------------
    # Friend requests
    # ------------------------------------------------------------------

    async def send_friend_request(
        self, username: str, message: str | None = None
    ) -> dict:
        target = await self.session.scalar(
            select(User).where(User.username == username, User.status == "active")
        )
        if target is None:
            raise ApiError(404, "NOT_FOUND", "用户不存在")
        if target.id == self.actor_id:
            raise ApiError(400, "INVALID", "不能向自己发送好友请求")
        if await self._is_contact(self.actor_id, target.id):
            raise ApiError(409, "CONFLICT", "对方已经是你的联系人")

        # Check for existing pending request in either direction
        existing = await self.session.scalar(
            select(FriendRequest).where(
                FriendRequest.status == "pending",
                (
                    (FriendRequest.from_user_id == self.actor_id)
                    & (FriendRequest.to_user_id == target.id)
                )
                | (
                    (FriendRequest.from_user_id == target.id)
                    & (FriendRequest.to_user_id == self.actor_id)
                ),
            )
        )
        if existing:
            raise ApiError(409, "CONFLICT", "已有待处理的好友请求")

        req = FriendRequest(
            id=str(uuid4()),
            from_user_id=self.actor_id,
            to_user_id=target.id,
            status="pending",
            message=message,
        )
        self.session.add(req)
        await self.session.commit()
        await self.session.refresh(req)

        return {
            "id": req.id,
            "from_user_id": req.from_user_id,
            "from_user_name": self.actor.username,
            "to_user_id": req.to_user_id,
            "to_user_name": target.username,
            "status": req.status,
            "message": req.message,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        }

    async def list_incoming_requests(self) -> list[dict]:
        rows = (
            (
                await self.session.scalars(
                    select(FriendRequest)
                    .options(selectinload(FriendRequest.from_user))
                    .where(
                        FriendRequest.to_user_id == self.actor_id,
                        FriendRequest.status == "pending",
                    )
                    .order_by(FriendRequest.created_at.desc())
                )
            )
            .all()
        )
        return [
            {
                "id": r.id,
                "from_user_id": r.from_user_id,
                "from_user_name": r.from_user.username,
                "to_user_id": r.to_user_id,
                "to_user_name": self.actor.username,
                "status": r.status,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def list_outgoing_requests(self) -> list[dict]:
        rows = (
            (
                await self.session.scalars(
                    select(FriendRequest)
                    .options(selectinload(FriendRequest.to_user))
                    .where(
                        FriendRequest.from_user_id == self.actor_id,
                        FriendRequest.status == "pending",
                    )
                    .order_by(FriendRequest.created_at.desc())
                )
            )
            .all()
        )
        return [
            {
                "id": r.id,
                "from_user_id": r.from_user_id,
                "from_user_name": self.actor.username,
                "to_user_id": r.to_user_id,
                "to_user_name": r.to_user.username,
                "status": r.status,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def handle_friend_request(self, request_id: str, action: str) -> dict:
        req = await self.session.scalar(
            select(FriendRequest)
            .options(selectinload(FriendRequest.from_user))
            .where(
                FriendRequest.id == request_id,
                FriendRequest.to_user_id == self.actor_id,
            )
        )
        if req is None:
            raise ApiError(404, "NOT_FOUND", "好友请求不存在")
        if req.status != "pending":
            raise ApiError(409, "CONFLICT", "该请求已被处理")

        if action == "accept":
            req.status = "accepted"
            # Create bidirectional contact entries
            for uid1, uid2 in [
                (self.actor_id, req.from_user_id),
                (req.from_user_id, self.actor_id),
            ]:
                existing = await self.session.get(Contact, (uid1, uid2))
                if existing is None:
                    self.session.add(
                        Contact(user_id=uid1, contact_id=uid2, status="active")
                    )
        elif action == "reject":
            req.status = "rejected"
        else:
            raise ApiError(400, "VALIDATION_ERROR", "无效操作")

        await self.session.commit()
        return {
            "id": req.id,
            "status": req.status,
        }

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def list_conversations(self) -> list[dict]:
        """List all conversations the current user is a member of,
        including last message and unread count."""
        conv_ids_q = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == self.actor_id)
        )
        conv_ids = (await self.session.scalars(conv_ids_q)).all()
        if not conv_ids:
            return []

        rows = (
            (
                await self.session.scalars(
                    select(Conversation)
                    .options(
                        selectinload(Conversation.members).selectinload(ConversationMember.user),
                        selectinload(Conversation.messages).limit(1).selectinload(Message.sender),
                    )
                    .where(Conversation.id.in_(conv_ids))
                    .order_by(Conversation.updated_at.desc())
                )
            )
            .all()
        )

        # Get the member record for unread count
        member_map: dict[str, ConversationMember] = {}
        for conv in rows:
            for m in conv.members:
                if m.user_id == self.actor_id:
                    member_map[conv.id] = m
                    break

        results = []
        for conv in rows:
            member = member_map.get(conv.id)
            unread = 0
            if member and member.last_read_at:
                unread_q = select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id,
                    Message.created_at > member.last_read_at,
                )
                unread = (await self.session.scalar(unread_q)) or 0

            last_msg = None
            if conv.messages:
                m = conv.messages[-1]
                last_msg = {
                    "content": m.content[:200],
                    "sender_name": m.sender.username if m.sender else "",
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }

            name = conv.name
            if conv.type == "private":
                # Show the other user's display name
                for m in conv.members:
                    if m.user_id != self.actor_id:
                        name = name or m.user.display_name
                        break

            results.append({
                "id": conv.id,
                "type": conv.type,
                "name": name,
                "unread_count": unread,
                "last_message": last_msg,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            })
        return results

    async def _get_or_create_private_conversation(self, other_user_id: str) -> str:
        """Return existing private conversation ID or create one."""
        # Find existing private conversation that has both users as members
        my_conv_ids = (
            await self.session.scalars(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.user_id == self.actor_id
                )
            )
        ).all()
        if my_conv_ids:
            match = await self.session.scalar(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.conversation_id.in_(my_conv_ids),
                    ConversationMember.user_id == other_user_id,
                )
            )
            if match:
                return match

        # Create new private conversation
        conv = Conversation(
            id=str(uuid4()),
            type="private",
            created_by=self.actor_id,
        )
        self.session.add(conv)
        await self.session.flush()

        now = utc_now()
        self.session.add(
            ConversationMember(
                conversation_id=conv.id, user_id=self.actor_id, role="owner",
                joined_at=now,
            )
        )
        self.session.add(
            ConversationMember(
                conversation_id=conv.id, user_id=other_user_id, role="owner",
                joined_at=now,
            )
        )
        await self.session.flush()
        return conv.id

    async def create_group_conversation(
        self, name: str | None, member_usernames: list[str]
    ) -> dict:
        # Resolve all member usernames
        users = (
            (
                await self.session.scalars(
                    select(User).where(
                        User.username.in_(member_usernames), User.status == "active"
                    )
                )
            )
            .all()
        )
        if len(users) != len(member_usernames):
            found = {u.username for u in users}
            missing = [n for n in member_usernames if n not in found]
            raise ApiError(400, "VALIDATION_ERROR", f"用户不存在或已禁用: {', '.join(missing)}")

        # Verify all are contacts
        for u in users:
            if u.id == self.actor_id:
                continue
            await self._assert_contact(self.actor_id, u.id)
            await self._assert_contact(u.id, self.actor_id)

        conv = Conversation(
            id=str(uuid4()),
            type="group",
            name=name,
            created_by=self.actor_id,
        )
        self.session.add(conv)
        await self.session.flush()

        now = utc_now()
        self.session.add(
            ConversationMember(
                conversation_id=conv.id, user_id=self.actor_id, role="owner",
                joined_at=now,
            )
        )
        for u in users:
            if u.id != self.actor_id:
                self.session.add(
                    ConversationMember(
                        conversation_id=conv.id, user_id=u.id, role="member",
                        joined_at=now,
                    )
                )
        await self.session.commit()
        await self.session.refresh(conv)

        return {
            "id": conv.id,
            "type": conv.type,
            "name": conv.name,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
        }

    async def get_conversation_members(self, conversation_id: str) -> list[dict]:
        await self._assert_conversation_member(conversation_id)
        rows = (
            (
                await self.session.scalars(
                    select(ConversationMember)
                    .options(selectinload(ConversationMember.user))
                    .where(ConversationMember.conversation_id == conversation_id)
                )
            )
            .all()
        )
        return [
            {
                "user_id": m.user_id,
                "username": m.user.username,
                "display_name": m.user.display_name,
                "role": m.role,
            }
            for m in rows
        ]

    async def leave_group(self, conversation_id: str) -> None:
        member = await self.session.get(
            ConversationMember, (conversation_id, self.actor_id)
        )
        if member is None:
            raise ApiError(404, "NOT_FOUND", "你不是该群聊的成员")
        conv = await self.session.get(Conversation, conversation_id)
        if conv is None or conv.type != "group":
            raise ApiError(400, "INVALID", "只能退出群聊")

        await self.session.delete(member)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def get_messages(
        self,
        conversation_id: str,
        before: str | None = None,
        after: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        await self._assert_conversation_member(conversation_id)

        query = (
            select(Message)
            .options(selectinload(Message.sender))
            .where(Message.conversation_id == conversation_id)
        )

        if before:
            ref = await self.session.get(Message, before)
            if ref:
                query = query.where(Message.created_at < ref.created_at)
        if after:
            ref = await self.session.get(Message, after)
            if ref:
                query = query.where(Message.created_at > ref.created_at)

        query = query.order_by(Message.created_at.desc()).limit(limit)
        rows = (await self.session.scalars(query)).all()
        rows = list(reversed(rows))  # Return in chronological order

        return [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_id": m.sender_id,
                "sender_name": m.sender.username if m.sender else "",
                "content_type": m.content_type,
                "content": m.content,
                "reply_to_id": m.reply_to_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]

    async def send_message(
        self,
        conversation_id: str,
        content_type: str,
        content: str,
        reply_to_id: str | None = None,
    ) -> dict:
        # Verify conversation exists
        conv = await self.session.get(Conversation, conversation_id)
        if conv is None:
            raise ApiError(404, "NOT_FOUND", "会话不存在")

        if conv.type == "private":
            # Ensure both users are still contacts (both directions)
            other_member = await self.session.scalar(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.user_id != self.actor_id,
                )
            )
            if other_member:
                if not await self._is_contact(self.actor_id, other_member):
                    raise ApiError(403, "FORBIDDEN", "对方不是你的联系人")
                if not await self._is_contact(other_member, self.actor_id):
                    raise ApiError(403, "FORBIDDEN", "对方已将你删除")
        else:
            # Group: just check membership
            await self._assert_conversation_member(conversation_id)

        msg = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            sender_id=self.actor_id,
            content_type=content_type,
            content=content,
            reply_to_id=reply_to_id,
        )
        self.session.add(msg)
        conv.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(msg)

        return {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "sender_name": self.actor.username,
            "content_type": msg.content_type,
            "content": msg.content,
            "reply_to_id": msg.reply_to_id,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }

    async def mark_read(
        self, conversation_id: str, last_read_message_id: str
    ) -> None:
        await self._assert_conversation_member(conversation_id)

        ref = await self.session.get(Message, last_read_message_id)
        if ref is None or ref.conversation_id != conversation_id:
            raise ApiError(400, "VALIDATION_ERROR", "消息不存在于该会话")

        member = await self.session.get(
            ConversationMember, (conversation_id, self.actor_id)
        )
        if member:
            member.last_read_at = ref.created_at
            await self.session.commit()
