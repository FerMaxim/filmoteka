import uuid
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


class AdoptUser(migrations.CreateModel):
    """Keep the original auth table, passwords, PKs and M2M relations on upgrade."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        user = to_state.apps.get_model(app_label, self.name)
        if (
            user._meta.db_table
            not in schema_editor.connection.introspection.table_names()
        ):
            return super().database_forwards(
                app_label, schema_editor, from_state, to_state
            )
        old_pk = models.AutoField(primary_key=True)
        old_pk.set_attributes_from_name("id")
        old_pk.model = user
        schema_editor.alter_field(user, old_pk, user._meta.pk)
        field = models.UUIDField(null=True)
        field.set_attributes_from_name("public_id")
        field.model = user
        schema_editor.add_field(user, field)
        quote = schema_editor.quote_name
        table = quote(user._meta.db_table)
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"SELECT id FROM {table}")
            for (pk,) in cursor.fetchall():
                cursor.execute(
                    f"UPDATE {table} SET public_id = %s WHERE id = %s",
                    [uuid.uuid4(), pk],
                )
        schema_editor.alter_field(user, field, user._meta.get_field("public_id"))
        schema_editor.execute(
            "UPDATE django_content_type SET app_label = 'accounts' WHERE app_label = 'auth' AND model = 'user'"
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        raise IrreversibleError(
            "User adoption preserves auth data; use a verified backup for rollback."
        )
