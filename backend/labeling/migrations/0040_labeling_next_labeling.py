import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labeling", "0039_alter_labeling_project_alter_labelingmembership_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="labeling",
            name="next_labeling",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="previous_labelings",
                to="labeling.labeling",
            ),
        ),
    ]
