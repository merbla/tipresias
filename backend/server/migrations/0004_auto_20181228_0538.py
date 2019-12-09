# Generated by Django 2.1.4 on 2018-12-28 05:38

from django.db import migrations, models
import server.models


class Migration(migrations.Migration):

    dependencies = [("server", "0003_auto_20181225_0646")]

    operations = [
        migrations.AddField(
            model_name="mlmodel",
            name="data_class_path",
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                validators=[server.models.ml_model.validate_module_path],
            ),
        ),
        migrations.AlterField(
            model_name="prediction",
            name="predicted_margin",
            field=models.PositiveSmallIntegerField(),
        ),
    ]
